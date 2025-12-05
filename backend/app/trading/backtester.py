"""
Backtesting engine for trading strategies.

Implements an event-driven backtest that evaluates strategy rules on historical
OHLCV data and generates trade logs with realistic metrics.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.core.logging import get_logger
from app.trading.indicators import evaluate_indicator, sma
from app.trading.models import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResult,
    EquityPoint,
    PortfolioEvaluationMode,
    RebalancingMode,
    Trade,
)

logger = get_logger(__name__)


def _normalize_rule_type(rule_type: str, indicator: str) -> str:
    """
    Normalize rule type by mapping semantic types (like "entry") to technical types.
    
    Args:
        rule_type: Original rule type (e.g., "entry", "exit", "crossover")
        indicator: Indicator name (e.g., "sma_cross", "sma", "ema")
    
    Returns:
        Normalized technical rule type (e.g., "crossover", "signal", "momentum")
    """
    # If already a technical type, return as-is
    if rule_type in ["crossover", "signal", "momentum", "mean_reversion"]:
        return rule_type
    
    # Map semantic types to technical types based on indicator
    indicator_lower = indicator.lower()
    
    if rule_type == "entry" or rule_type == "exit":
        # Map entry/exit rules based on indicator name
        if "cross" in indicator_lower or "crossover" in indicator_lower:
            return "crossover"
        elif "momentum" in indicator_lower:
            return "momentum"
        elif "mean_reversion" in indicator_lower or "reversion" in indicator_lower:
            return "mean_reversion"
        else:
            # Default to signal for other indicators
            return "signal"
    
    # Unknown type, return as-is (will be handled by error case)
    return rule_type


def _evaluate_strategy_rule(rule_type: str, indicator: str, params: Dict, prices: List[float], current_idx: int, is_exit: bool = False) -> bool:
    """
    Evaluate a single strategy rule at a given index.

    Args:
        rule_type: Type of rule (e.g., "signal", "crossover", "entry")
        indicator: Indicator name (e.g., "sma", "ema", "sma_cross")
        params: Rule parameters
        prices: Price series
        current_idx: Current bar index

    Returns:
        True if rule condition is met, False otherwise
    """
    if current_idx < 1:
        return False

    try:
        # Normalize rule type (e.g., "entry" -> "crossover" or "signal")
        normalized_type = _normalize_rule_type(rule_type, indicator)
        
        # Handle crossover rules first (they don't use evaluate_indicator)
        if normalized_type == "crossover":
            # Moving average crossover: fast MA crosses above/below slow MA
            # Support both "fast_window"/"slow_window" and "fast"/"slow" parameter names
            fast_window = params.get("fast_window") or params.get("fast", 10)
            slow_window = params.get("slow_window") or params.get("slow", 20)
            # Default direction: "above" for entry, "below" for exit
            default_direction = "below" if is_exit else "above"
            direction = params.get("direction", default_direction)  # "above" for bullish, "below" for bearish

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

        elif normalized_type == "signal":
            # Signal rule: uses evaluate_indicator
            from app.trading.indicators import evaluate_indicator

            indicator_values = evaluate_indicator(indicator, prices, params)

            if current_idx >= len(indicator_values) or np.isnan(indicator_values[current_idx]):
                return False

            current_value = indicator_values[current_idx]
            threshold = params.get("threshold", 0.0)
            direction = params.get("direction", "above")  # "above" or "below"
            if direction == "above":
                return current_value > threshold
            else:
                return current_value < threshold

        elif normalized_type == "momentum":
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

        elif normalized_type == "mean_reversion":
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
            logger.warning(f"Unknown rule type: {rule_type} (normalized: {normalized_type})")
            return False

    except Exception as e:
        logger.error(f"Error evaluating rule: {e}", exc_info=True)
        return False


def _parse_rebalancing_frequency(frequency: str) -> timedelta:
    """Parse rebalancing frequency string (e.g., '1d', '1w') into timedelta."""
    if not frequency:
        return timedelta(days=1)
    
    frequency = frequency.lower().strip()
    if frequency.endswith('d'):
        days = int(frequency[:-1])
        return timedelta(days=days)
    elif frequency.endswith('w'):
        weeks = int(frequency[:-1])
        return timedelta(weeks=weeks)
    elif frequency.endswith('m'):
        months = int(frequency[:-1])
        return timedelta(days=months * 30)  # Approximate
    else:
        return timedelta(days=1)


def _should_rebalance(
    rebalancing_mode: RebalancingMode,
    last_rebalance_time: Optional[datetime],
    current_time: datetime,
    rebalancing_frequency: Optional[str],
    has_signal_change: bool,
) -> bool:
    """Determine if portfolio should be rebalanced."""
    if rebalancing_mode == RebalancingMode.SIGNAL_BASED:
        return has_signal_change
    elif rebalancing_mode == RebalancingMode.TIME_BASED:
        if not last_rebalance_time or not rebalancing_frequency:
            return True  # First rebalance
        frequency_delta = _parse_rebalancing_frequency(rebalancing_frequency)
        return (current_time - last_rebalance_time) >= frequency_delta
    elif rebalancing_mode == RebalancingMode.BOTH:
        time_based = False
        if last_rebalance_time and rebalancing_frequency:
            frequency_delta = _parse_rebalancing_frequency(rebalancing_frequency)
            time_based = (current_time - last_rebalance_time) >= frequency_delta
        return time_based or has_signal_change
    return False


def _evaluate_strategy_rules(strategy_rules: List, prices: List[float], current_idx: int, filter_type: Optional[str] = None) -> bool:
    """
    Evaluate strategy rules (AND logic - all must be true).

    Args:
        strategy_rules: List of StrategyRule objects
        prices: Price series
        current_idx: Current bar index
        filter_type: Optional filter to only evaluate rules of this type (e.g., "entry", "exit")

    Returns:
        True if all filtered rules are satisfied
    """
    if not strategy_rules:
        return False

    # Filter rules by type if filter_type is specified
    filtered_rules = strategy_rules
    if filter_type:
        filtered_rules = [rule for rule in strategy_rules if rule.type == filter_type]
        # If no rules match the filter, return False
        if not filtered_rules:
            return False

    # Evaluate all filtered rules (AND logic)
    is_exit = filter_type == "exit" if filter_type else False
    for rule in filtered_rules:
        rule_type = rule.type
        indicator = rule.indicator
        params = rule.params or {}

        if not _evaluate_strategy_rule(rule_type, indicator, params, prices, current_idx, is_exit=is_exit):
            return False

    return True


def _create_unified_timeline(ohlcv_data: Dict[str, List[Dict]]) -> List[Tuple[datetime, str, int]]:
    """
    Create a unified timeline of all events across all symbols.
    
    Returns:
        List of (timestamp, symbol, bar_index) tuples sorted by timestamp
    """
    timeline = []
    for symbol, bars in ohlcv_data.items():
        for idx, bar in enumerate(bars):
            timestamp = bar["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            timeline.append((timestamp, symbol, idx))
    
    # Sort by timestamp
    timeline.sort(key=lambda x: x[0])
    return timeline


def _get_price_at_index(symbol: str, idx: int, ohlcv_data: Dict[str, List[Dict]]) -> Optional[float]:
    """Get price at a specific index for a symbol."""
    bars = ohlcv_data.get(symbol, [])
    if 0 <= idx < len(bars):
        return bars[idx]["close"]
    return None


def _rebalance_portfolio(
    portfolio_value: float,
    positions: Dict[str, Dict[str, float]],
    target_allocations: Dict[str, float],
    current_prices: Dict[str, float],
    cash: float,
    commission_rate: float,
    slippage_pct: float,
    current_timestamp: datetime,
) -> Tuple[float, List[Trade]]:
    """
    Rebalance portfolio to target allocations.
    
    Returns:
        Tuple of (new_cash, list_of_trades)
    """
    trades: List[Trade] = []
    new_cash = cash
    
    # Calculate current allocations
    current_values: Dict[str, float] = {}
    for symbol, pos_info in positions.items():
        if symbol in current_prices:
            current_values[symbol] = pos_info["quantity"] * current_prices[symbol]
    
    # Calculate target values
    target_values: Dict[str, float] = {}
    for symbol, allocation in target_allocations.items():
        if symbol in current_prices:
            target_values[symbol] = portfolio_value * allocation
    
    # Generate rebalancing trades
    for symbol in set(list(positions.keys()) + list(target_allocations.keys())):
        current_qty = positions.get(symbol, {}).get("quantity", 0.0)
        current_value = current_values.get(symbol, 0.0)
        target_value = target_values.get(symbol, 0.0)
        price = current_prices.get(symbol, 0.0)
        
        if price <= 0:
            continue
        
        target_qty = target_value / price if target_value > 0 else 0.0
        qty_diff = target_qty - current_qty
        
        if abs(qty_diff) < 0.01:  # Skip dust
            continue
        
        if qty_diff > 0:
            # Buy
            fill_price = price * (1 + slippage_pct)
            cost = qty_diff * fill_price
            commission = cost * commission_rate
            total_cost = cost + commission
            
            if new_cash >= total_cost:
                new_cash -= total_cost
                current_qty = positions.get(symbol, {}).get("quantity", 0.0)
                positions[symbol] = {
                    "quantity": current_qty + qty_diff,
                    "entry_price": fill_price,
                    "entry_idx": -1,  # Rebalance doesn't track entry_idx
                }
                trades.append(
                    Trade(
                        timestamp=current_timestamp,
                        symbol=symbol,
                        side="buy",
                        quantity=qty_diff,
                        price=fill_price,
                    )
                )
        else:
            # Sell
            qty_to_sell = abs(qty_diff)
            fill_price = price * (1 - slippage_pct)
            proceeds = qty_to_sell * fill_price
            commission = proceeds * commission_rate
            net_proceeds = proceeds - commission
            
            new_cash += net_proceeds
            current_qty = positions.get(symbol, {}).get("quantity", 0.0)
            positions[symbol] = {
                "quantity": max(0.0, current_qty - qty_to_sell),
                "entry_price": positions.get(symbol, {}).get("entry_price", fill_price),
                "entry_idx": positions.get(symbol, {}).get("entry_idx", -1),
            }
            trades.append(
                Trade(
                    timestamp=current_timestamp,
                    symbol=symbol,
                    side="sell",
                    quantity=qty_to_sell,
                    price=fill_price,
                )
            )
    
    return new_cash, trades


def run_backtest(request: BacktestRequest, ohlcv_data: Optional[Dict[str, List[Dict]]] = None) -> BacktestResult:
    """
    Run a backtest on a strategy using historical OHLCV data.
    Supports multi-symbol portfolios with configurable evaluation modes and rebalancing.

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
        timeframe = getattr(request, "timeframe", "1d")  # Get timeframe from request, default to "1d"
        ohlcv_data = market_data.load_data(universe=universe, start=start_dt, end=end_dt, timeframe=timeframe)

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
    # Track positions per symbol: symbol -> {quantity, entry_price, entry_idx}
    positions: Dict[str, Dict[str, float]] = {}
    portfolio_values: List[float] = []
    equity_timestamps: List[datetime] = []
    trades: List[Trade] = []

    # Get costs
    commission_rate = request.costs.get("commission", 0.001)
    slippage_pct = request.costs.get("slippage_pct", 0.0005)

    # Get strategy parameters
    params = strategy.params
    evaluation_mode = params.evaluation_mode if hasattr(params, 'evaluation_mode') else PortfolioEvaluationMode.PER_SYMBOL
    rebalancing_mode = params.rebalancing_mode if hasattr(params, 'rebalancing_mode') else RebalancingMode.SIGNAL_BASED
    rebalancing_frequency = params.rebalancing_frequency if hasattr(params, 'rebalancing_frequency') else None
    max_positions = params.max_positions if hasattr(params, 'max_positions') else None

    # Process each symbol in universe
    universe = strategy.universe or list(ohlcv_data.keys())
    if not universe:
        universe = list(ohlcv_data.keys())

    # Validate we have data for all symbols
    for symbol in universe:
        if symbol not in ohlcv_data or not ohlcv_data[symbol]:
            logger.warning(f"No bars for symbol {symbol}, removing from universe")
            universe = [s for s in universe if s != symbol]
    
    if not universe:
        logger.error("No valid symbols in universe after validation")
        return BacktestResult(
            strategy=strategy,
            metrics=BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0),
            trade_log=[],
        )

    # For backward compatibility: if only one symbol and PER_SYMBOL mode, use simplified logic
    timeline = None  # Initialize timeline for single-symbol path
    if len(universe) == 1 and evaluation_mode == PortfolioEvaluationMode.PER_SYMBOL:
        # Use original single-symbol logic for backward compatibility
        primary_symbol = universe[0]
        bars = ohlcv_data[primary_symbol]
        prices = [bar["close"] for bar in bars]
        timestamps = [bar["timestamp"] for bar in bars]
        
        # Convert string timestamps to datetime if needed
        if isinstance(timestamps[0], str):
            timestamps = [datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps]

        # Separate entry and exit rules
        entry_rules = [rule for rule in strategy.rules if rule.type == "entry"]
        exit_rules = [rule for rule in strategy.rules if rule.type == "exit"]
        
        if not entry_rules and not exit_rules:
            entry_rules = strategy.rules
            exit_rules = []
            logger.debug("No explicit entry/exit rules found, treating all rules as entry rules")

        in_position = False
        last_rebalance_time: Optional[datetime] = None

        # Record initial portfolio value at the first bar (index 0)
        if len(bars) > 0:
            portfolio_values.append(initial_cash)
            equity_timestamps.append(timestamps[0])

        # Event-driven backtest loop
        for i in range(1, len(bars)):
            current_price = prices[i]
            current_timestamp = timestamps[i]

            # Check rebalancing
            has_signal_change = False
            if not in_position:
                entry_signal = _evaluate_strategy_rules(entry_rules, prices, i, filter_type="entry") if entry_rules else False
                exit_signal = False
                if entry_signal:
                    has_signal_change = True
            else:
                entry_signal = False
                exit_signal = _evaluate_strategy_rules(exit_rules, prices, i, filter_type="exit") if exit_rules else False
                if exit_signal:
                    has_signal_change = True

            # Calculate portfolio value
            portfolio_value = cash
            for sym, pos_info in positions.items():
                if sym == primary_symbol:
                    portfolio_value += pos_info["quantity"] * current_price
            portfolio_values.append(portfolio_value)
            equity_timestamps.append(current_timestamp)

            # Check if rebalancing is needed
            should_rebalance = _should_rebalance(
                rebalancing_mode,
                last_rebalance_time,
                current_timestamp,
                rebalancing_frequency,
                has_signal_change,
            )

            # Trading logic: enter/exit positions
            if entry_signal and not in_position:
                if params.position_sizing == "fixed_fraction" and params.fraction:
                    target_value = portfolio_value * params.fraction
                else:
                    target_value = 1000.0

                quantity = target_value / current_price if current_price > 0 else 0.0
                quantity = round(quantity, 2)

                if quantity > 0 and cash >= target_value:
                    fill_price = current_price * (1 + slippage_pct)
                    cost = quantity * fill_price
                    commission = cost * commission_rate
                    total_cost = cost + commission

                    if cash >= total_cost:
                        cash -= total_cost
                        positions[primary_symbol] = {
                            "quantity": quantity,
                            "entry_price": fill_price,
                            "entry_idx": i,
                        }
                        in_position = True

                        trades.append(
                            Trade(
                                timestamp=current_timestamp,
                                symbol=primary_symbol,
                                side="buy",
                                quantity=quantity,
                                price=fill_price,
                            )
                        )

            elif exit_signal and in_position:
                quantity = positions.get(primary_symbol, {}).get("quantity", 0.0)
                if quantity > 0:
                    fill_price = current_price * (1 - slippage_pct)
                    proceeds = quantity * fill_price
                    commission = proceeds * commission_rate
                    net_proceeds = proceeds - commission

                    cash += net_proceeds
                    positions[primary_symbol] = {"quantity": 0.0, "entry_price": 0.0, "entry_idx": -1}
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

            if should_rebalance:
                last_rebalance_time = current_timestamp

        # Close any remaining positions at end
        if in_position:
            final_price = prices[-1]
            quantity = positions.get(primary_symbol, {}).get("quantity", 0.0)
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

        # Calculate final portfolio value for single-symbol path
        final_portfolio_value = cash
        remaining_quantity = positions.get(primary_symbol, {}).get("quantity", 0.0)
        if remaining_quantity > 0.01:
            final_price = prices[-1]
            final_portfolio_value += remaining_quantity * final_price
        portfolio_values.append(final_portfolio_value)
        equity_timestamps.append(timestamps[-1])
        
        # Set timeline to None to indicate single-symbol path was used
        # This prevents NameError in shared code below
        # Note: Final portfolio value already calculated above, so shared code will skip it
        timeline = None

    else:
        # Multi-symbol portfolio logic
        # Create unified timeline
        timeline = _create_unified_timeline(ohlcv_data)
        
        if not timeline:
            logger.error("No timeline events created")
            return BacktestResult(
                strategy=strategy,
                metrics=BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0),
                trade_log=[],
            )

        # Separate entry and exit rules
        entry_rules = [rule for rule in strategy.rules if rule.type == "entry"]
        exit_rules = [rule for rule in strategy.rules if rule.type == "exit"]
        
        if not entry_rules and not exit_rules:
            entry_rules = strategy.rules
            exit_rules = []

        # Track signals per symbol
        symbol_signals: Dict[str, Dict[str, bool]] = {}  # symbol -> {entry: bool, exit: bool}
        last_rebalance_time: Optional[datetime] = None
        symbol_prices: Dict[str, List[float]] = {}
        symbol_timestamps: Dict[str, List[datetime]] = {}
        
        # Pre-process prices for each symbol
        for symbol in universe:
            bars = ohlcv_data[symbol]
            symbol_prices[symbol] = [bar["close"] for bar in bars]
            timestamps = [bar["timestamp"] for bar in bars]
            if isinstance(timestamps[0], str):
                symbol_timestamps[symbol] = [datetime.fromisoformat(ts.replace("Z", "+00:00")) for ts in timestamps]
            else:
                symbol_timestamps[symbol] = timestamps

        # Record initial portfolio value at the earliest timestamp
        if timeline:
            portfolio_values.append(initial_cash)
            equity_timestamps.append(timeline[0][0])

        # Process timeline events
        for timestamp, symbol, bar_idx in timeline:
            if symbol not in universe:
                continue
            
            prices = symbol_prices[symbol]
            if bar_idx >= len(prices) or bar_idx < 1:
                continue

            current_price = prices[bar_idx]
            in_position = positions.get(symbol, {}).get("quantity", 0.0) > 0.01

            # Evaluate signals
            prev_entry = symbol_signals.get(symbol, {}).get("entry", False)
            prev_exit = symbol_signals.get(symbol, {}).get("exit", False)
            
            if not in_position:
                entry_signal = _evaluate_strategy_rules(entry_rules, prices, bar_idx, filter_type="entry") if entry_rules else False
                exit_signal = False
            else:
                entry_signal = False
                exit_signal = _evaluate_strategy_rules(exit_rules, prices, bar_idx, filter_type="exit") if exit_rules else False

            symbol_signals[symbol] = {"entry": entry_signal, "exit": exit_signal}
            has_signal_change = (entry_signal != prev_entry) or (exit_signal != prev_exit)

            # Calculate portfolio value
            portfolio_value = cash
            current_prices: Dict[str, float] = {}
            for sym in universe:
                sym_bars = ohlcv_data[sym]
                # Find the most recent bar index (max) rather than first match (next)
                matching_indices = [idx for ts, s, idx in timeline if s == sym and ts <= timestamp]
                sym_idx = max(matching_indices) if matching_indices else (len(sym_bars) - 1)
                if sym_idx < len(sym_bars):
                    current_prices[sym] = sym_bars[sym_idx]["close"]
                    pos_info = positions.get(sym, {})
                    portfolio_value += pos_info.get("quantity", 0.0) * current_prices[sym]
            
            portfolio_values.append(portfolio_value)
            equity_timestamps.append(timestamp)

            # Check rebalancing
            should_rebalance = _should_rebalance(
                rebalancing_mode,
                last_rebalance_time,
                timestamp,
                rebalancing_frequency,
                has_signal_change,
            )

            if evaluation_mode == PortfolioEvaluationMode.PER_SYMBOL:
                # Per-symbol evaluation: each symbol trades independently
                if entry_signal and not in_position:
                    if params.position_sizing == "fixed_fraction" and params.fraction:
                        target_value = portfolio_value * params.fraction
                    else:
                        target_value = 1000.0

                    quantity = target_value / current_price if current_price > 0 else 0.0
                    quantity = round(quantity, 2)

                    if quantity > 0:
                        fill_price = current_price * (1 + slippage_pct)
                        cost = quantity * fill_price
                        commission = cost * commission_rate
                        total_cost = cost + commission

                        if cash >= total_cost:
                            cash -= total_cost
                            positions[symbol] = {
                                "quantity": quantity,
                                "entry_price": fill_price,
                                "entry_idx": bar_idx,
                            }
                            trades.append(
                                Trade(
                                    timestamp=timestamp,
                                    symbol=symbol,
                                    side="buy",
                                    quantity=quantity,
                                    price=fill_price,
                                )
                            )

                elif exit_signal and in_position:
                    quantity = positions.get(symbol, {}).get("quantity", 0.0)
                    if quantity > 0:
                        fill_price = current_price * (1 - slippage_pct)
                        proceeds = quantity * fill_price
                        commission = proceeds * commission_rate
                        net_proceeds = proceeds - commission

                        cash += net_proceeds
                        positions[symbol] = {"quantity": 0.0, "entry_price": 0.0, "entry_idx": -1}
                        trades.append(
                            Trade(
                                timestamp=timestamp,
                                symbol=symbol,
                                side="sell",
                                quantity=quantity,
                                price=fill_price,
                            )
                        )

            elif evaluation_mode == PortfolioEvaluationMode.PORTFOLIO_LEVEL:
                # Portfolio-level evaluation: aggregate signals and allocate capital
                if should_rebalance:
                    # Rank symbols by signal strength (simple: entry signal = 1, exit signal = -1)
                    symbol_scores: Dict[str, float] = {}
                    for sym in universe:
                        sym_signals = symbol_signals.get(sym, {})
                        if sym_signals.get("entry", False):
                            symbol_scores[sym] = 1.0
                        elif sym_signals.get("exit", False):
                            symbol_scores[sym] = -1.0
                        else:
                            symbol_scores[sym] = 0.0
                    
                    # Select top N symbols
                    sorted_symbols = sorted(symbol_scores.items(), key=lambda x: x[1], reverse=True)
                    selected_symbols = [sym for sym, score in sorted_symbols if score > 0]
                    if max_positions:
                        selected_symbols = selected_symbols[:max_positions]
                    
                    # Equal-weight allocation
                    if selected_symbols:
                        allocation_per_symbol = 1.0 / len(selected_symbols)
                        target_allocations = {sym: allocation_per_symbol for sym in selected_symbols}
                        
                        # Close positions not in target
                        for sym in list(positions.keys()):
                            if sym not in target_allocations:
                                pos_info = positions.get(sym, {})
                                qty = pos_info.get("quantity", 0.0)
                                if qty > 0.01 and sym in current_prices:
                                    fill_price = current_prices[sym] * (1 - slippage_pct)
                                    proceeds = qty * fill_price
                                    commission = proceeds * commission_rate
                                    net_proceeds = proceeds - commission
                                    cash += net_proceeds
                                    positions[sym] = {"quantity": 0.0, "entry_price": 0.0, "entry_idx": -1}
                                    trades.append(
                                        Trade(
                                            timestamp=timestamp,
                                            symbol=sym,
                                            side="sell",
                                            quantity=qty,
                                            price=fill_price,
                                        )
                                    )
                        
                        # Rebalance to target allocations
                        new_cash, rebalance_trades = _rebalance_portfolio(
                            portfolio_value,
                            positions,
                            target_allocations,
                            current_prices,
                            cash,
                            commission_rate,
                            slippage_pct,
                            timestamp,
                        )
                        cash = new_cash
                        trades.extend(rebalance_trades)
                        last_rebalance_time = timestamp

            if should_rebalance and evaluation_mode == PortfolioEvaluationMode.PER_SYMBOL:
                last_rebalance_time = timestamp

        # Close any remaining positions at end
        final_timestamp = timeline[-1][0] if timeline else datetime.utcnow()
        for symbol, pos_info in list(positions.items()):
            quantity = pos_info.get("quantity", 0.0)
            if quantity > 0.01:
                bars = ohlcv_data.get(symbol, [])
                if bars:
                    final_price = bars[-1]["close"]
                    fill_price = final_price * (1 - slippage_pct)
                    proceeds = quantity * fill_price
                    commission = proceeds * commission_rate
                    net_proceeds = proceeds - commission
                    cash += net_proceeds

                    trades.append(
                        Trade(
                            timestamp=final_timestamp,
                            symbol=symbol,
                            side="sell",
                            quantity=quantity,
                            price=fill_price,
                        )
                    )

    # Calculate final portfolio value (only for multi-symbol path)
    # Single-symbol path already calculated this above
    if timeline is not None:
        # Multi-symbol path: calculate final portfolio value
        final_portfolio_value = cash
        final_timestamp = timeline[-1][0] if timeline else datetime.utcnow()
        for symbol, pos_info in positions.items():
            bars = ohlcv_data.get(symbol, [])
            if bars:
                final_price = bars[-1]["close"]
                final_portfolio_value += pos_info.get("quantity", 0.0) * final_price
        portfolio_values.append(final_portfolio_value)
        equity_timestamps.append(final_timestamp)
    # Single-symbol path: final portfolio value already calculated and appended above

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

    # Build equity curve from portfolio values and timestamps
    equity_curve: Optional[List[EquityPoint]] = None
    if len(portfolio_values) == len(equity_timestamps) and len(portfolio_values) > 0:
        equity_curve = [
            EquityPoint(timestamp=ts, value=val)
            for ts, val in zip(equity_timestamps, portfolio_values)
        ]

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

    return BacktestResult(strategy=strategy, metrics=metrics, trade_log=trades, equity_curve=equity_curve)
