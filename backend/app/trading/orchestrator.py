from datetime import datetime, timedelta
from typing import List

from app.agents.strategy_planner import generate_strategy_specs
from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading import market_data
from app.trading.backtester import run_backtest
from app.trading.broker_alpaca import get_alpaca_broker
from app.trading.models import (
    BacktestRequest,
    CandidateResult,
    PortfolioState,
    StrategyRunRequest,
    StrategyRunResponse,
    StrategySpec,
)
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

    candidates: List[CandidateResult] = []
    for spec in strategies:
        bt_request = BacktestRequest(
            strategy=spec,
            data_range=data_range,
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )
        backtest_result = run_backtest(bt_request)

        # Simple risk & execution flow (execution can be disabled via context flag).
        portfolio = PortfolioState(cash=100_000.0, positions=[])
        # For now, we don't generate detailed proposed orders from trades; this is a placeholder.
        proposed_orders = []
        assessment = risk_assess(portfolio=portfolio, proposed_trades=proposed_orders)

        if context.get("execute", False) and assessment.approved_trades:
            broker = get_alpaca_broker()
            broker.execute_orders(assessment.approved_trades)

        candidates.append(
            CandidateResult(
                strategy=spec,
                backtest=backtest_result,
                risk=assessment,
            )
        )

    run_id = f"run_{int(datetime.utcnow().timestamp())}"
    return StrategyRunResponse(
        run_id=run_id,
        mission=mission,
        candidates=candidates,
        created_at=datetime.utcnow(),
    )



