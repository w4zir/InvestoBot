"""
Backtesting engine for trading strategies.

Implements an event-driven backtest that evaluates strategy rules on historical
OHLCV data and generates trade logs with realistic metrics.
"""
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

from app.core.logging import get_logger
from app.trading.indicators import evaluate_indicator, sma
from app.trading.models import BacktestMetrics, BacktestRequest, BacktestResult, Trade

logger = get_logger(__name__)


def _evaluate_strategy_rule(rule_type: str, indicator: str, params: Dict, prices: List[float], current_idx: int) -> bool:
    """
    Evaluate a single strategy rule at a given index.

    Args:
        rule_type: Type of rule (e.g., "signal", "crossover")
        indicator: Indicator name (e.g., "sma", "ema")
        params: Rule parameters
        prices: Price series
        current_idx: Current bar index

    Returns:
        True if rule condition is met, False otherwise
    """
    if current_idx < 1:
        return False

    try:
        from app.trading.indicators import evaluate_indicator

        indicator_values = evaluate_indicator(indicator, prices, params)

        if current_idx >= len(indicator_values) or np.isnan(indicator_values[current_idx]):
            return False

        current_value = indicator_values[current_idx]
        prev_value = indicator_values[current_idx - 1] if current_idx > 0 else float("nan")

        if rule_type == "signal":
            threshold = params.get("threshold", 0.0)
            direction = params.get("direction", "above")  # "above" or "below"
            if direction == "above":
                return current_value > threshold
            else:
                return current_value < threshold

        elif rule_type == "crossover":
            # Moving average crossover: fast MA crosses above/below slow MA
            fast_window = params.get("fast_window", 10)
            slow_window = params.get("slow_window", 20)
            direction = params.get("direction", "above")  # "above" for bullish, "below" for bearish

            fast_ma = sma(prices, fast_window)
            slow_ma = sma(prices, slow_window)

            if current_idx < slow_window - 1:
                return False

            fast_current = fast_ma[current_idx]
            slow_current = slow_ma[current_idx]
            fast_prev = fast_ma[current_idx - 1] if current_idx > 0 else float("nan")
            slow_prev = slow_ma[current_idx - 1] if current_idx > 0 else float("nan")

            if np.isnan(fast_current) or np.isnan(slow_current) or np.isnan(fast_prev) or np.isnan(slow_prev):
                return False

            if direction == "above":
                # Bullish crossover: fast crosses above slow
                return fast_prev <= slow_prev and fast_current > slow_current
            else:
                # Bearish crossover: fast crosses below slow
                return fast_prev >= slow_prev and fast_current < slow_current

        elif rule_type == "momentum":
            # Price momentum: price > MA and recent return > threshold
            window = params.get("window", 20)
            return_threshold = params.get("return_threshold", 0.02)

            if current_idx < window:
                return False

            ma_values = sma(prices, window)
            if np.isnan(ma_values[current_idx]):
                return False

            current_price = prices[current_idx]
            price_above_ma = current_price > ma_values[current_idx]

            # Calculate recent return
            lookback = params.get("lookback", 5)
            if current_idx >= lookback:
                past_price = prices[current_idx - lookback]
                recent_return = (current_price - past_price) / past_price if past_price > 0 else 0.0
                return price_above_ma and recent_return > return_threshold
            else:
                return price_above_ma

        elif rule_type == "mean_reversion":
            # Mean reversion: Z-score indicates oversold/overbought
            window = params.get("window", 20)
            threshold = params.get("threshold", 2.0)
            direction = params.get("direction", "below")  # "below" for oversold (buy), "above" for overbought (sell)

            from app.trading.indicators import calculate_returns, zscore

            returns = calculate_returns(prices)
            zscores = zscore(returns, window)

            if current_idx >= len(zscores) or np.isnan(zscores[current_idx]):
                return False

            z = zscores[current_idx]
            if direction == "below":
                return z < -threshold  # Oversold, buy signal
            else:
                return z > threshold  # Overbought, sell signal

        else:
            logger.warning(f"Unknown rule type: {rule_type}")
            return False

    except Exception as e:
        logger.error(f"Error evaluating rule: {e}", exc_info=True)
        return False


def _evaluate_strategy_rules(strategy_rules: List, prices: List[float], current_idx: int) -> bool:
    """
    Evaluate all strategy rules (AND logic - all must be true).

    Args:
        strategy_rules: List of StrategyRule objects
        prices: Price series
        current_idx: Current bar index

    Returns:
        True if all rules are satisfied
    """
    if not strategy_rules:
        return False

    for rule in strategy_rules:
        rule_type = rule.type
        indicator = rule.indicator
        params = rule.params or {}

        if not _evaluate_strategy_rule(rule_type, indicator, params, prices, current_idx):
            return False

    return True


def run_backtest(request: BacktestRequest, ohlcv_data: Optional[Dict[str, List[Dict]]] = None) -> BacktestResult:
    """
    Run a backtest on a strategy using historical OHLCV data.

    Args:
        request: BacktestRequest with strategy, data_range, and costs
        ohlcv_data: Optional pre-loaded OHLCV data (if None, will be loaded)

    Returns:
        BacktestResult with metrics and trade log
    """
    strategy = request.strategy
    logger.info("Running backtest", extra={"strategy_id": strategy.strategy_id})

    # Load OHLCV data if not provided
    if ohlcv_data is None:
        from app.trading import market_data
        from app.trading.orchestrator import _parse_date_range

        start_dt, end_dt = _parse_date_range(request.data_range)
        universe = strategy.universe or ["AAPL"]
        ohlcv_data = market_data.load_data(universe=universe, start=start_dt, end=end_dt)

    if not ohlcv_data:
        logger.error("No OHLCV data available for backtest")
        return BacktestResult(
            strategy=strategy,
            metrics=BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0),
            trade_log=[],
        )

    # Initialize backtest state
    initial_cash = 100_000.0
    cash = initial_cash
    positions: Dict[str, float] = {}  # symbol -> quantity
    portfolio_values: List[float] = []
    trades: List[Trade] = []

    # Get costs
    commission_rate = request.costs.get("commission", 0.001)
    slippage_pct = request.costs.get("slippage_pct", 0.0005)

    # Process each symbol in universe
    universe = strategy.universe or list(ohlcv_data.keys())
    if not universe:
        universe = list(ohlcv_data.keys())

    # For simplicity, we'll backtest on the first symbol or combine signals
    # In a more sophisticated version, we'd handle multi-symbol portfolios
    primary_symbol = universe[0] if universe else list(ohlcv_data.keys())[0]
    bars = ohlcv_data.get(primary_symbol, [])

    if not bars:
        logger.warning(f"No bars for primary symbol {primary_symbol}")
        return BacktestResult(
            strategy=strategy,
            metrics=BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0),
            trade_log=[],
        )

    # Extract prices
    prices = [bar["close"] for bar in bars]
    timestamps = [bar["timestamp"] for bar in bars]

    # Track position state (long/flat)
    in_position = False
    entry_price = 0.0
    entry_idx = -1

    # Event-driven backtest loop
    for i in range(1, len(bars)):  # Start from 1 to have previous bar for indicators
        current_price = prices[i]
        current_timestamp = timestamps[i]

        # Evaluate strategy rules
        signal = _evaluate_strategy_rules(strategy.rules, prices, i)

        # Calculate portfolio value
        portfolio_value = cash
        for sym, qty in positions.items():
            # For simplicity, use current price for all positions
            portfolio_value += qty * current_price
        portfolio_values.append(portfolio_value)

        # Trading logic: enter/exit positions
        if signal and not in_position:
            # Enter long position
            params = strategy.params
            if params.position_sizing == "fixed_fraction" and params.fraction:
                target_value = portfolio_value * params.fraction
            else:
                target_value = 1000.0  # Default fixed size

            # Calculate quantity
            quantity = target_value / current_price if current_price > 0 else 0.0
            quantity = round(quantity, 2)

            if quantity > 0 and cash >= target_value:
                # Apply slippage
                fill_price = current_price * (1 + slippage_pct)
                cost = quantity * fill_price
                commission = cost * commission_rate
                total_cost = cost + commission

                if cash >= total_cost:
                    cash -= total_cost
                    positions[primary_symbol] = positions.get(primary_symbol, 0.0) + quantity
                    in_position = True
                    entry_price = fill_price
                    entry_idx = i

                    trades.append(
                        Trade(
                            timestamp=current_timestamp,
                            symbol=primary_symbol,
                            side="buy",
                            quantity=quantity,
                            price=fill_price,
                        )
                    )
                    logger.debug(
                        f"Entered position: {quantity} shares of {primary_symbol} at {fill_price}",
                        extra={"idx": i, "price": fill_price, "quantity": quantity},
                    )

        elif not signal and in_position:
            # Exit position
            quantity = positions.get(primary_symbol, 0.0)
            if quantity > 0:
                # Apply slippage
                fill_price = current_price * (1 - slippage_pct)
                proceeds = quantity * fill_price
                commission = proceeds * commission_rate
                net_proceeds = proceeds - commission

                cash += net_proceeds
                positions[primary_symbol] = 0.0
                in_position = False

                trades.append(
                    Trade(
                        timestamp=current_timestamp,
                        symbol=primary_symbol,
                        side="sell",
                        quantity=quantity,
                        price=fill_price,
                    )
                )
                logger.debug(
                    f"Exited position: {quantity} shares of {primary_symbol} at {fill_price}",
                    extra={"idx": i, "price": fill_price, "quantity": quantity},
                )

    # Close any remaining positions at end
    if in_position:
        final_price = prices[-1]
        quantity = positions.get(primary_symbol, 0.0)
        if quantity > 0:
            fill_price = final_price * (1 - slippage_pct)
            proceeds = quantity * fill_price
            commission = proceeds * commission_rate
            net_proceeds = proceeds - commission
            cash += net_proceeds

            trades.append(
                Trade(
                    timestamp=timestamps[-1],
                    symbol=primary_symbol,
                    side="sell",
                    quantity=quantity,
                    price=fill_price,
                )
            )

    # Calculate final portfolio value
    final_portfolio_value = cash
    for sym, qty in positions.items():
        final_price = prices[-1] if sym == primary_symbol else 0.0
        final_portfolio_value += qty * final_price
    portfolio_values.append(final_portfolio_value)

    # Calculate metrics
    if len(portfolio_values) < 2:
        metrics = BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0)
    else:
        # Calculate returns
        returns = []
        for i in range(1, len(portfolio_values)):
            if portfolio_values[i - 1] > 0:
                ret = (portfolio_values[i] - portfolio_values[i - 1]) / portfolio_values[i - 1]
                returns.append(ret)
            else:
                returns.append(0.0)

        if not returns:
            metrics = BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0)
        else:
            # Total return
            total_return = (final_portfolio_value - initial_cash) / initial_cash

            # Sharpe ratio (annualized, assuming 252 trading days)
            mean_return = np.mean(returns) if returns else 0.0
            std_return = np.std(returns) if len(returns) > 1 else 0.0
            if std_return > 0:
                sharpe = (mean_return / std_return) * (252 ** 0.5)  # Annualized
            else:
                sharpe = 0.0

            # Max drawdown
            peak = initial_cash
            max_dd = 0.0
            for pv in portfolio_values:
                if pv > peak:
                    peak = pv
                dd = (peak - pv) / peak if peak > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd

            metrics = BacktestMetrics(sharpe=sharpe, max_drawdown=max_dd, total_return=total_return)

    logger.info(
        f"Backtest complete: {len(trades)} trades, Sharpe={metrics.sharpe:.2f}, Return={metrics.total_return:.2%}",
        extra={
            "strategy_id": strategy.strategy_id,
            "trades_count": len(trades),
            "sharpe": metrics.sharpe,
            "total_return": metrics.total_return,
            "max_drawdown": metrics.max_drawdown,
        },
    )

    return BacktestResult(strategy=strategy, metrics=metrics, trade_log=trades)
