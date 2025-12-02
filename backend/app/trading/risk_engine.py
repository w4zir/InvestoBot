from typing import List

from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading.models import Order, PortfolioState, RiskAssessment


logger = get_logger(__name__)
settings = get_settings()


def risk_assess(portfolio: PortfolioState, proposed_trades: List[Order]) -> RiskAssessment:
    """
    Simple deterministic risk checks based on notional limits and blacklist.
    """
    approved: List[Order] = []
    violations: List[str] = []

    blacklist = set(settings.risk.blacklist_symbols)

    for order in proposed_trades:
        if order.symbol in blacklist:
            violations.append(f"Symbol {order.symbol} is blacklisted")
            continue

        # Very naive notional check using a fixed reference price.
        notional = abs(order.quantity) * (order.limit_price or 100.0)
        if notional > settings.risk.max_trade_notional:
            violations.append(
                f"Order for {order.symbol} exceeds max trade notional ({notional} > {settings.risk.max_trade_notional})"
            )
            continue

        approved.append(order)

    return RiskAssessment(approved_trades=approved, violations=violations)



