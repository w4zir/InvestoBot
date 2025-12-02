from typing import Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading.models import Order, PortfolioState, RiskAssessment


logger = get_logger(__name__)
settings = get_settings()


def risk_assess(portfolio: PortfolioState, proposed_trades: List[Order], latest_prices: Optional[Dict[str, float]] = None) -> RiskAssessment:
    """
    Simple deterministic risk checks based on notional limits and blacklist.

    Args:
        portfolio: Current portfolio state
        proposed_trades: List of proposed orders
        latest_prices: Optional dict of latest prices per symbol (for notional calculation)

    Returns:
        RiskAssessment with approved trades and violations
    """
    approved: List[Order] = []
    violations: List[str] = []

    blacklist = set(settings.risk.blacklist_symbols)

    # Calculate total portfolio value for exposure checks
    portfolio_value = portfolio.cash
    if latest_prices:
        for pos in portfolio.positions:
            if pos.symbol in latest_prices:
                portfolio_value += pos.quantity * latest_prices[pos.symbol]

    for order in proposed_trades:
        if order.symbol in blacklist:
            violations.append(f"Symbol {order.symbol} is blacklisted")
            continue

        # Calculate notional using latest price or limit price
        price = order.limit_price
        if price is None and latest_prices and order.symbol in latest_prices:
            price = latest_prices[order.symbol]
        elif price is None:
            price = 100.0  # Fallback to default

        notional = abs(order.quantity) * price

        # Check max trade notional
        if notional > settings.risk.max_trade_notional:
            violations.append(
                f"Order for {order.symbol} exceeds max trade notional ({notional:.2f} > {settings.risk.max_trade_notional:.2f})"
            )
            continue

        # Check portfolio exposure (optional, lightweight check)
        if portfolio_value > 0:
            exposure = notional / portfolio_value
            if exposure > settings.risk.max_portfolio_exposure:
                violations.append(
                    f"Order for {order.symbol} exceeds max portfolio exposure ({exposure:.2%} > {settings.risk.max_portfolio_exposure:.2%})"
                )
                continue

        approved.append(order)

    return RiskAssessment(approved_trades=approved, violations=violations)



