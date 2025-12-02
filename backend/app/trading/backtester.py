from typing import Dict, List

from app.core.logging import get_logger
from app.trading.models import BacktestMetrics, BacktestRequest, BacktestResult, Trade


logger = get_logger(__name__)


def run_backtest(request: BacktestRequest) -> BacktestResult:
    """
    Extremely simplified backtest implementation.

    This is a placeholder: it generates a trivial trade log and dummy
    metrics so the orchestration and API surface can be exercised.
    """
    strategy = request.strategy
    logger.info("Running placeholder backtest", extra={"strategy_id": strategy.strategy_id})

    trades: List[Trade] = []
    # In a real implementation, iterate over OHLCV data and create trades based on rules.
    # Here, we simply create a single synthetic trade for demonstration.
    from datetime import datetime

    trades.append(
        Trade(
            timestamp=datetime.utcnow(),
            symbol=(strategy.universe[0] if strategy.universe else "AAPL"),
            side="buy",
            quantity=1.0,
            price=100.0,
        )
    )

    metrics = BacktestMetrics(sharpe=1.0, max_drawdown=0.1, total_return=0.05)
    return BacktestResult(strategy=strategy, metrics=metrics, trade_log=trades)



