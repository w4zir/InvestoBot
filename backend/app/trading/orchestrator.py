import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.agents.strategy_planner import generate_strategy_specs
from app.core.config import get_settings
from app.core.logging import add_log_context, get_logger, LogContext
from app.core.repository import RunRepository
from app.routes.control import is_kill_switch_enabled
from app.trading import market_data
from app.trading.backtester import run_backtest
from app.trading.broker_manager import get_broker
from app.trading.models import (
    BacktestRequest,
    CandidateResult,
    Fill,
    GatingResult,
    PortfolioState,
    StrategyRunRequest,
    StrategyRunResponse,
    StrategySpec,
    ValidationConfig,
    WalkForwardResult,
)
from app.trading.order_generator import generate_orders
from app.trading.persistence import get_persistence_service
from app.trading.risk_engine import risk_assess
from app.trading.scenarios import evaluate_gates, list_scenarios
from app.trading.validation import run_walk_forward_backtest


logger = get_logger(__name__)
settings = get_settings()

# Initialize repository for persistence
_repository = RunRepository()


def _default_date_range() -> str:
    end = datetime.utcnow().date()
    start = end - timedelta(days=settings.data.default_lookback_days)
    return f"{start.isoformat()}:{end.isoformat()}"


def _update_portfolio_after_execution(
    portfolio: PortfolioState,
    fills: List[Fill],
    latest_prices: Dict[str, float],
) -> PortfolioState:
    """
    Update portfolio state after order execution based on fills.
    
    Args:
        portfolio: Current portfolio state
        fills: List of fills from executed orders
        latest_prices: Latest prices for calculating position values
    
    Returns:
        Updated PortfolioState
    """
    from app.trading.models import PortfolioPosition
    
    # Create a dict of current positions for easy lookup
    positions_dict: Dict[str, PortfolioPosition] = {
        pos.symbol: pos for pos in portfolio.positions
    }
    
    # Update cash and positions based on fills
    new_cash = portfolio.cash
    
    for fill in fills:
        symbol = fill.symbol
        quantity = fill.quantity
        price = fill.price
        
        if fill.side == "buy":
            # Buying: reduce cash, add/update position
            cost = quantity * price
            new_cash -= cost
            
            if symbol in positions_dict:
                # Update existing position (weighted average price)
                existing = positions_dict[symbol]
                total_qty = existing.quantity + quantity
                if total_qty > 0:
                    avg_price = ((existing.quantity * existing.average_price) + cost) / total_qty
                    positions_dict[symbol] = PortfolioPosition(
                        symbol=symbol,
                        quantity=total_qty,
                        average_price=avg_price,
                    )
                else:
                    # Position closed, remove it
                    del positions_dict[symbol]
            else:
                # New position
                positions_dict[symbol] = PortfolioPosition(
                    symbol=symbol,
                    quantity=quantity,
                    average_price=price,
                )
        else:  # sell
            # Selling: increase cash, reduce/remove position
            proceeds = quantity * price
            new_cash += proceeds
            
            if symbol in positions_dict:
                existing = positions_dict[symbol]
                new_qty = existing.quantity - quantity
                if new_qty > 0:
                    # Reduce position, keep average price
                    positions_dict[symbol] = PortfolioPosition(
                        symbol=symbol,
                        quantity=new_qty,
                        average_price=existing.average_price,
                    )
                else:
                    # Position closed, remove it
                    del positions_dict[symbol]
    
    return PortfolioState(
        cash=new_cash,
        positions=list(positions_dict.values()),
    )


def _parse_date_range(dr: str) -> tuple[datetime, datetime]:
    try:
        start_s, end_s = dr.split(":")
        # Handle date-only strings (YYYY-MM-DD) by adding time component
        if len(start_s) == 10:  # Date only format
            start_dt = datetime.fromisoformat(f"{start_s}T00:00:00")
        else:
            start_dt = datetime.fromisoformat(start_s)
        
        if len(end_s) == 10:  # Date only format
            end_dt = datetime.fromisoformat(f"{end_s}T00:00:00")
        else:
            end_dt = datetime.fromisoformat(end_s)
        
        return start_dt, end_dt
    except ValueError as e:
        logger.error(f"Failed to parse date range '{dr}': {e}", exc_info=True)
        raise ValueError(f"Invalid date range format '{dr}'. Expected format: 'YYYY-MM-DD:YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS:YYYY-MM-DDTHH:MM:SS'")


def run_strategy_run(payload: StrategyRunRequest) -> StrategyRunResponse:
    """
    High-level orchestration:
    - Ask Google Agent for candidate strategies.
    - Backtest each candidate.
    - Apply risk engine and optionally execute via Alpaca.
    """
    # Check kill switch before proceeding
    if is_kill_switch_enabled():
        error_msg = "Strategy execution blocked: kill switch is enabled"
        logger.warning(error_msg, extra={"mission": payload.mission})
        raise ValueError(error_msg)
    
    mission = payload.mission
    context = payload.context

    universe = context.get("universe") or settings.data.default_universe
    data_range = context.get("data_range") or _default_date_range()
    timeframe = context.get("timeframe") or settings.data.default_timeframe

    # Add log context for the run
    run_id = f"run_{int(datetime.utcnow().timestamp())}"
    add_log_context("run_id", run_id)
    
    logger.info(
        "Starting strategy run",
        extra={"mission": mission, "universe": universe, "data_range": data_range, "timeframe": timeframe, "run_id": run_id},
    )

    strategies: List[StrategySpec] = generate_strategy_specs(mission=mission, context=context)

    start_dt, end_dt = _parse_date_range(data_range)
    ohlcv = market_data.load_data(universe=universe, start=start_dt, end=end_dt, timeframe=timeframe)

    # Determine portfolio state: fetch from Alpaca if executing, otherwise use synthetic
    should_execute = context.get("execute", False)
    if should_execute:
        try:
            broker = get_broker()
            portfolio = broker.get_positions()
            logger.info("Fetched portfolio from Alpaca", extra={"cash": portfolio.cash, "positions_count": len(portfolio.positions)})
        except Exception as e:
            logger.error("Failed to fetch portfolio from Alpaca, using synthetic", exc_info=True)
            portfolio = PortfolioState(cash=100_000.0, positions=[])
    else:
        portfolio = PortfolioState(cash=100_000.0, positions=[])

    # Extract latest prices from OHLCV data (use last bar's close price)
    latest_prices: Dict[str, float] = {}
    for symbol, bars in ohlcv.items():
        if bars:
            latest_prices[symbol] = bars[-1]["close"]
    
    # Save initial portfolio snapshot
    try:
        persistence = get_persistence_service()
        persistence.save_portfolio_snapshot(
            portfolio_state=portfolio,
            run_id=run_id,
            snapshot_type="initial",
            notes="Initial portfolio state at start of strategy run",
            latest_prices=latest_prices,
        )
    except Exception as e:
        logger.warning(f"Failed to save initial portfolio snapshot: {e}", exc_info=True)

    # Extract validation and scenario configuration from context
    validation_config_dict = context.get("validation", {})
    validation_config = ValidationConfig(**validation_config_dict) if validation_config_dict else ValidationConfig()
    
    # Get scenario configuration
    enable_scenarios = context.get("enable_scenarios", False)
    scenario_tags = context.get("scenario_tags", None)  # Optional filter by tags
    gating_override = context.get("gating_override", False)  # Override gating failures

    candidates: List[CandidateResult] = []
    for spec in strategies:
        bt_request = BacktestRequest(
            strategy=spec,
            data_range=data_range,
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        # Run walk-forward validation if enabled
        walk_forward_result: Optional[WalkForwardResult] = None
        if validation_config.walk_forward or validation_config.train_split > 0:
            logger.info(f"Running walk-forward validation for strategy {spec.strategy_id}")
            try:
                walk_forward_result = run_walk_forward_backtest(bt_request, ohlcv, validation_config)
                # Use the aggregate metrics from walk-forward as the primary backtest result
                from app.trading.models import BacktestResult
                backtest_result = BacktestResult(
                    strategy=spec,
                    metrics=walk_forward_result.aggregate_metrics,
                    trade_log=walk_forward_result.windows[0].trade_log if walk_forward_result.windows else [],
                )
            except Exception as e:
                logger.error(f"Walk-forward validation failed for strategy {spec.strategy_id}: {e}", exc_info=True)
                # Fall back to regular backtest
                backtest_result = run_backtest(bt_request, ohlcv_data=ohlcv)
        else:
            backtest_result = run_backtest(bt_request, ohlcv_data=ohlcv)

        # Run scenario evaluation and gating if enabled
        gating_result: Optional[GatingResult] = None
        if enable_scenarios:
            logger.info(f"Running scenario evaluation for strategy {spec.strategy_id}")
            try:
                scenarios = list_scenarios(tags=scenario_tags) if scenario_tags else list_scenarios()
                if scenarios:
                    gating_result = evaluate_gates(bt_request, scenarios, ohlcv)
                    logger.info(
                        f"Scenario gating for strategy {spec.strategy_id}: passed={gating_result.overall_passed}, "
                        f"violations={len(gating_result.blocking_violations)}"
                    )
                else:
                    logger.warning("No scenarios found for evaluation")
            except Exception as e:
                logger.error(f"Scenario evaluation failed for strategy {spec.strategy_id}: {e}", exc_info=True)

        # Generate orders from strategy and backtest results
        proposed_orders = generate_orders(
            strategy=spec,
            portfolio=portfolio,
            latest_prices=latest_prices,
            backtest_trades=backtest_result.trade_log,
        )
        logger.info(
            f"Generated {len(proposed_orders)} orders for strategy {spec.strategy_id}",
            extra={"strategy_id": spec.strategy_id, "order_count": len(proposed_orders)},
        )

        # Risk assessment with enhanced context (equity curve and historical data)
        use_agent = context.get("use_risk_agent", False)  # Optional: enable agent-based risk assessment
        assessment = risk_assess(
            portfolio=portfolio,
            proposed_trades=proposed_orders,
            latest_prices=latest_prices,
            equity_curve=backtest_result.equity_curve,  # Pass equity curve for drawdown calculation
            historical_data=ohlcv,  # Pass historical data for correlation and liquidity checks
            use_agent=use_agent,
        )
        logger.info(
            f"Risk assessment for strategy {spec.strategy_id}: {len(assessment.approved_trades)} approved, "
            f"{len(assessment.violations)} violations, {len(assessment.warnings)} warnings, "
            f"risk_level={assessment.risk_level.value}, risk_score={assessment.risk_score}",
            extra={
                "strategy_id": spec.strategy_id,
                "approved_count": len(assessment.approved_trades),
                "violations_count": len(assessment.violations),
                "warnings_count": len(assessment.warnings),
                "risk_level": assessment.risk_level.value,
                "risk_score": assessment.risk_score,
                "drawdown_blocked": assessment.drawdown_blocked,
                "current_drawdown": assessment.current_drawdown,
                "var_estimate": assessment.var_estimate,
            },
        )

        # Check gating before execution
        execution_blocked = False
        execution_error: Optional[str] = None
        if gating_result and not gating_result.overall_passed:
            if not gating_override:
                execution_blocked = True
                execution_error = f"Execution blocked by gating rules: {', '.join(gating_result.blocking_violations[:3])}"
                logger.warning(
                    f"Execution blocked for strategy {spec.strategy_id} due to gating violations",
                    extra={"violations": gating_result.blocking_violations},
                )
            else:
                logger.warning(
                    f"Gating failed for strategy {spec.strategy_id} but execution allowed due to override flag"
                )

        # Save pre-execution portfolio snapshot
        if should_execute and assessment.approved_trades and not execution_blocked:
            try:
                persistence = get_persistence_service()
                persistence.save_portfolio_snapshot(
                    portfolio_state=portfolio,
                    run_id=run_id,
                    strategy_id=spec.strategy_id,
                    snapshot_type="pre_execution",
                    notes=f"Portfolio state before executing {len(assessment.approved_trades)} approved orders",
                    latest_prices=latest_prices,
                )
            except Exception as e:
                logger.warning(f"Failed to save pre-execution portfolio snapshot: {e}", exc_info=True)
        
        # Execute orders if enabled and approved
        fills: List[Fill] = []
        if should_execute and assessment.approved_trades and not execution_blocked:
            # Safety check: only execute in non-dev environments or with explicit flag
            allow_execute = settings.env != "dev" or os.getenv("ALLOW_EXECUTE", "false").lower() == "true"
            if not allow_execute:
                logger.warning("Execution blocked: dev environment without ALLOW_EXECUTE flag")
                execution_error = "Execution blocked: dev environment without ALLOW_EXECUTE flag"
            else:
                try:
                    broker = get_broker()
                    fills = broker.execute_orders(assessment.approved_trades)
                    logger.info(
                        f"Executed {len(fills)} orders for strategy {spec.strategy_id}",
                        extra={"strategy_id": spec.strategy_id, "fill_count": len(fills)},
                    )
                    
                    # Update portfolio state after execution
                    portfolio = _update_portfolio_after_execution(portfolio, fills, latest_prices)
                    logger.info(
                        f"Updated portfolio after execution: cash={portfolio.cash:.2f}, positions={len(portfolio.positions)}",
                        extra={"strategy_id": spec.strategy_id},
                    )
                    
                    # Save post-execution portfolio snapshot
                    try:
                        persistence = get_persistence_service()
                        persistence.save_portfolio_snapshot(
                            portfolio_state=portfolio,
                            run_id=run_id,
                            strategy_id=spec.strategy_id,
                            snapshot_type="post_execution",
                            notes=f"Portfolio state after executing {len(fills)} fills",
                            latest_prices=latest_prices,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save post-execution portfolio snapshot: {e}", exc_info=True)
                except RuntimeError as e:
                    # Broker is unavailable (e.g., Alpaca not configured)
                    error_msg = str(e)
                    if "No available broker" in error_msg:
                        execution_error = (
                            "Broker is not configured or unavailable. "
                            "Please configure Alpaca API keys (ALPACA_API_KEY, ALPACA_SECRET_KEY) "
                            "in backend/.env to execute trades. Using paper trading keys is recommended."
                        )
                    else:
                        execution_error = f"Broker error: {error_msg}"
                    logger.warning(
                        f"Cannot execute orders for strategy {spec.strategy_id}: broker unavailable",
                        extra={"strategy_id": spec.strategy_id, "error": error_msg}
                    )
                except Exception as e:
                    logger.error(f"Failed to execute orders for strategy {spec.strategy_id}", exc_info=True)
                    execution_error = f"Execution failed: {str(e)}"

        candidates.append(
            CandidateResult(
                strategy=spec,
                backtest=backtest_result,
                risk=assessment,
                execution_fills=fills,
                execution_error=execution_error,
                validation=walk_forward_result,
                gating=gating_result,
            )
        )

    # Create response (run_id was set earlier)
    response = StrategyRunResponse(
        run_id=run_id,
        mission=mission,
        candidates=candidates,
        created_at=datetime.utcnow(),
    )
    
    # Persist to database (non-blocking - failures are logged but don't fail the run)
    try:
        with LogContext(run_id=run_id, mission=mission):
            logger.info("Persisting strategy run to database", extra={"run_id": run_id, "candidate_count": len(candidates)})
            success = _repository.save_strategy_run(response, context)
            if success:
                logger.info("Successfully persisted strategy run", extra={"run_id": run_id})
            else:
                logger.warning("Failed to persist strategy run (database may be unavailable)", extra={"run_id": run_id})
    except Exception as e:
        # Log but don't fail the run if persistence fails
        logger.error(f"Error persisting strategy run: {e}", exc_info=True, extra={"run_id": run_id})
    
    return response



