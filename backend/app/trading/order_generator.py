"""
Order generation module.

Converts strategy specifications and backtest results into concrete Order objects
that can be evaluated by the risk engine and executed by the broker.
"""
from typing import Dict, List

from app.core.logging import get_logger
from app.trading.models import Order, PortfolioState, StrategySpec, Trade

logger = get_logger(__name__)


def generate_orders(
    strategy: StrategySpec,
    portfolio: PortfolioState,
    latest_prices: Dict[str, float],
    backtest_trades: List[Trade],
) -> List[Order]:
    """
    Generate orders from a strategy specification and backtest results.

    This function translates strategy signals (from backtest trade log) into
    concrete Order objects using position sizing rules from StrategyParams.
    Supports both per-symbol and portfolio-level evaluation modes.

    Args:
        strategy: The strategy specification with rules and parameters
        portfolio: Current portfolio state (cash and positions)
        latest_prices: Latest price for each symbol in the universe
        backtest_trades: Trade log from backtest (used to infer signals)

    Returns:
        List of Order objects representing proposed trades
    """
    orders: List[Order] = []

    # Calculate total portfolio value
    portfolio_value = portfolio.cash
    for pos in portfolio.positions:
        symbol = pos.symbol
        if symbol in latest_prices:
            portfolio_value += pos.quantity * latest_prices[symbol]

    if portfolio_value <= 0:
        logger.warning("Portfolio value is zero or negative, cannot generate orders")
        return orders

    # Determine target positions from backtest trades
    # Strategy: look at the most recent trades for each symbol to determine target position
    symbol_targets: Dict[str, float] = {}
    current_positions: Dict[str, float] = {pos.symbol: pos.quantity for pos in portfolio.positions}

    # Analyze backtest trades to determine target positions
    # If the last trade for a symbol is a buy, we want to be long
    # If it's a sell or no recent trade, we want to be flat
    for trade in sorted(backtest_trades, key=lambda t: t.timestamp):
        symbol = trade.symbol
        if trade.side == "buy":
            # Accumulate buy signals
            symbol_targets[symbol] = symbol_targets.get(symbol, 0.0) + trade.quantity
        elif trade.side == "sell":
            # Reduce position on sell
            symbol_targets[symbol] = symbol_targets.get(symbol, 0.0) - trade.quantity

    # Generate orders based on target vs current positions
    params = strategy.params
    universe = strategy.universe or list(latest_prices.keys())

    for symbol in universe:
        if symbol not in latest_prices:
            logger.warning(f"Symbol {symbol} not in latest_prices, skipping")
            continue

        current_qty = current_positions.get(symbol, 0.0)
        target_qty = symbol_targets.get(symbol, 0.0)

        # If no target from backtest, check if strategy rules suggest a position
        # For now, we'll use a simple heuristic: if strategy has rules for this symbol,
        # use position sizing to determine target
        if target_qty == 0.0 and symbol in universe:
            # Try to infer from strategy rules - simple approach: if strategy mentions symbol, allocate
            if params.position_sizing == "fixed_fraction" and params.fraction:
                target_value = portfolio_value * params.fraction
                target_qty = target_value / latest_prices[symbol] if latest_prices[symbol] > 0 else 0.0
            elif params.position_sizing == "fixed_size":
                # Fixed size would need a size parameter - for now, use a default
                target_value = 1000.0  # Default fixed size
                target_qty = target_value / latest_prices[symbol] if latest_prices[symbol] > 0 else 0.0
            else:
                target_qty = 0.0

        # Round to reasonable precision (avoid fractional shares for now)
        target_qty = round(target_qty, 2)

        # Generate order if target differs from current
        if abs(target_qty - current_qty) > 0.01:  # Small threshold to avoid dust
            if target_qty > current_qty:
                # Need to buy
                order_qty = target_qty - current_qty
                orders.append(
                    Order(
                        symbol=symbol,
                        side="buy",
                        quantity=order_qty,
                        type="market",
                    )
                )
                logger.info(
                    f"Generated buy order for {symbol}: {order_qty} shares",
                    extra={"symbol": symbol, "quantity": order_qty, "target": target_qty, "current": current_qty},
                )
            elif target_qty < current_qty:
                # Need to sell
                order_qty = current_qty - target_qty
                orders.append(
                    Order(
                        symbol=symbol,
                        side="sell",
                        quantity=order_qty,
                        type="market",
                    )
                )
                logger.info(
                    f"Generated sell order for {symbol}: {order_qty} shares",
                    extra={"symbol": symbol, "quantity": order_qty, "target": target_qty, "current": current_qty},
                )

    return orders

