import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.agents.strategy_planner import generate_strategy_specs
from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading import market_data
from app.trading.backtester import run_backtest
from app.trading.broker_alpaca import get_alpaca_broker
from app.trading.models import (
    BacktestRequest,
    CandidateResult,
    Fill,
    PortfolioState,
    StrategyRunRequest,
    StrategyRunResponse,
    StrategySpec,
)
from app.trading.order_generator import generate_orders
from app.trading.risk_engine import risk_assess


logger = get_logger(__name__)
settings = get_settings()


def _default_date_range() -> str:
    end = datetime.utcnow().date()
    start = end - timedelta(days=settings.data.default_lookback_days)
    return f"{start.isoformat()}:{end.isoformat()}"


def _parse_date_range(dr: str) -> tuple[datetime, datetime]:
    start_s, end_s = dr.split(":")
    return datetime.fromisoformat(start_s), datetime.fromisoformat(end_s)


def run_strategy_run(payload: StrategyRunRequest) -> StrategyRunResponse:
    """
    High-level orchestration:
    - Ask Google Agent for candidate strategies.
    - Backtest each candidate.
    - Apply risk engine and optionally execute via Alpaca.
    """
    mission = payload.mission
    context = payload.context

    universe = context.get("universe") or settings.data.default_universe
    data_range = context.get("data_range") or _default_date_range()

    logger.info(
        "Starting strategy run",
        extra={"mission": mission, "universe": universe, "data_range": data_range},
    )

    strategies: List[StrategySpec] = generate_strategy_specs(mission=mission, context=context)

    start_dt, end_dt = _parse_date_range(data_range)
    ohlcv = market_data.load_data(universe=universe, start=start_dt, end=end_dt)

    # Determine portfolio state: fetch from Alpaca if executing, otherwise use synthetic
    should_execute = context.get("execute", False)
    if should_execute:
        try:
            broker = get_alpaca_broker()
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

    candidates: List[CandidateResult] = []
    for spec in strategies:
        bt_request = BacktestRequest(
            strategy=spec,
            data_range=data_range,
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )
        backtest_result = run_backtest(bt_request, ohlcv_data=ohlcv)

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

        # Risk assessment
        assessment = risk_assess(portfolio=portfolio, proposed_trades=proposed_orders, latest_prices=latest_prices)
        logger.info(
            f"Risk assessment for strategy {spec.strategy_id}: {len(assessment.approved_trades)} approved, {len(assessment.violations)} violations",
            extra={
                "strategy_id": spec.strategy_id,
                "approved_count": len(assessment.approved_trades),
                "violations_count": len(assessment.violations),
            },
        )

        # Execute orders if enabled and approved
        fills: List[Fill] = []
        execution_error: Optional[str] = None
        if should_execute and assessment.approved_trades:
            # Safety check: only execute in non-dev environments or with explicit flag
            allow_execute = settings.env != "dev" or os.getenv("ALLOW_EXECUTE", "false").lower() == "true"
            if not allow_execute:
                logger.warning("Execution blocked: dev environment without ALLOW_EXECUTE flag")
                execution_error = "Execution blocked: dev environment without ALLOW_EXECUTE flag"
            else:
                try:
                    broker = get_alpaca_broker()
                    fills = broker.execute_orders(assessment.approved_trades)
                    logger.info(
                        f"Executed {len(fills)} orders for strategy {spec.strategy_id}",
                        extra={"strategy_id": spec.strategy_id, "fill_count": len(fills)},
                    )
                except Exception as e:
                    logger.error(f"Failed to execute orders for strategy {spec.strategy_id}", exc_info=True)
                    execution_error = str(e)

        candidates.append(
            CandidateResult(
                strategy=spec,
                backtest=backtest_result,
                risk=assessment,
                execution_fills=fills,
                execution_error=execution_error,
            )
        )

    run_id = f"run_{int(datetime.utcnow().timestamp())}"
    return StrategyRunResponse(
        run_id=run_id,
        mission=mission,
        candidates=candidates,
        created_at=datetime.utcnow(),
    )



