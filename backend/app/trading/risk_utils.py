"""
Risk utility functions for calculating drawdown, liquidity, correlation, and VaR.

These functions support the risk engine's deterministic risk checks.
"""
from typing import Dict, List, Tuple, Set
import statistics
import math


def calculate_drawdown(portfolio_values: List[float]) -> Tuple[float, float]:
    """
    Calculate current drawdown from portfolio values.
    
    Args:
        portfolio_values: List of portfolio values over time
        
    Returns:
        Tuple of (current_drawdown, max_drawdown) as decimals (0.0 to 1.0)
    """
    if not portfolio_values or len(portfolio_values) < 2:
        return 0.0, 0.0
    
    # Find peak value
    peak = max(portfolio_values)
    if peak == 0:
        return 0.0, 0.0
    
    # Current value is the last one
    current = portfolio_values[-1]
    
    # Calculate current drawdown
    current_drawdown = (peak - current) / peak if peak > 0 else 0.0
    
    # Calculate max drawdown (largest drop from any peak)
    max_drawdown = 0.0
    running_peak = portfolio_values[0]
    for value in portfolio_values[1:]:
        if value > running_peak:
            running_peak = value
        else:
            drawdown = (running_peak - value) / running_peak if running_peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)
    
    return current_drawdown, max_drawdown


def get_avg_daily_volume(
    symbol: str,
    historical_data: List[Dict],
    lookback_days: int = 30
) -> float:
    """
    Calculate average daily volume from historical OHLCV data.
    
    Args:
        symbol: Symbol name (for logging)
        historical_data: List of OHLCV bars with 'volume' field
        lookback_days: Number of days to look back (default: 30)
        
    Returns:
        Average daily volume (float)
    """
    if not historical_data:
        return 0.0
    
    # Take last N bars (or all if fewer)
    recent_bars = historical_data[-lookback_days:] if len(historical_data) > lookback_days else historical_data
    
    volumes = []
    for bar in recent_bars:
        if 'volume' in bar and bar['volume'] is not None:
            volumes.append(float(bar['volume']))
    
    if not volumes:
        return 0.0
    
    return statistics.mean(volumes)


def check_liquidity(
    symbol: str,
    notional: float,
    avg_daily_volume: float,
    min_avg_volume: float,
    min_volume_ratio: float
) -> Tuple[bool, str]:
    """
    Check if a trade has sufficient liquidity.
    
    Args:
        symbol: Symbol name
        notional: Trade notional value (quantity * price)
        avg_daily_volume: Average daily volume
        min_avg_volume: Minimum average volume threshold
        min_volume_ratio: Minimum ratio of trade size to daily volume
        
    Returns:
        Tuple of (is_valid, message)
    """
    # Check minimum average volume
    if avg_daily_volume < min_avg_volume:
        return False, f"Symbol {symbol} has insufficient average daily volume ({avg_daily_volume:,.0f} < {min_avg_volume:,.0f})"
    
    # Check trade size relative to daily volume
    if avg_daily_volume > 0:
        volume_ratio = notional / avg_daily_volume
        if volume_ratio > min_volume_ratio:
            return False, f"Trade size for {symbol} is too large relative to daily volume ({volume_ratio:.2%} > {min_volume_ratio:.2%})"
    
    return True, ""


def calculate_correlation_matrix(
    symbols: List[str],
    historical_returns: Dict[str, List[float]],
    min_periods: int = 20
) -> Dict[str, Dict[str, float]]:
    """
    Calculate correlation matrix between symbols based on historical returns.
    
    Args:
        symbols: List of symbols to correlate
        historical_returns: Dict mapping symbol to list of returns
        min_periods: Minimum number of periods required for correlation
        
    Returns:
        Nested dict: correlations[symbol1][symbol2] = correlation coefficient
    """
    correlations: Dict[str, Dict[str, float]] = {}
    
    for symbol1 in symbols:
        correlations[symbol1] = {}
        returns1 = historical_returns.get(symbol1, [])
        
        if len(returns1) < min_periods:
            # Not enough data, set correlation to 0
            for symbol2 in symbols:
                correlations[symbol1][symbol2] = 0.0
            continue
        
        for symbol2 in symbols:
            if symbol1 == symbol2:
                correlations[symbol1][symbol2] = 1.0
            else:
                returns2 = historical_returns.get(symbol2, [])
                
                if len(returns2) < min_periods:
                    correlations[symbol1][symbol2] = 0.0
                else:
                    # Align returns (take minimum length)
                    min_len = min(len(returns1), len(returns2))
                    aligned_returns1 = returns1[-min_len:]
                    aligned_returns2 = returns2[-min_len:]
                    
                    # Calculate Pearson correlation
                    try:
                        corr = _pearson_correlation(aligned_returns1, aligned_returns2)
                        correlations[symbol1][symbol2] = corr
                    except Exception:
                        correlations[symbol1][symbol2] = 0.0
    
    return correlations


def _pearson_correlation(x: List[float], y: List[float]) -> float:
    """Calculate Pearson correlation coefficient between two lists."""
    if len(x) != len(y) or len(x) == 0:
        return 0.0
    
    try:
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)
        
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
        sum_sq_x = sum((x[i] - mean_x) ** 2 for i in range(len(x)))
        sum_sq_y = sum((y[i] - mean_y) ** 2 for i in range(len(y)))
        
        denominator = math.sqrt(sum_sq_x * sum_sq_y)
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    except Exception:
        return 0.0


def group_correlated_symbols(
    symbols: List[str],
    correlations: Dict[str, Dict[str, float]],
    threshold: float = 0.7
) -> List[Set[str]]:
    """
    Group symbols that are highly correlated.
    
    Args:
        symbols: List of symbols
        correlations: Correlation matrix from calculate_correlation_matrix
        threshold: Correlation threshold for grouping (default: 0.7)
        
    Returns:
        List of sets, where each set contains correlated symbols
    """
    groups: List[Set[str]] = []
    processed: Set[str] = set()
    
    for symbol in symbols:
        if symbol in processed:
            continue
        
        # Find all symbols correlated with this one
        group = {symbol}
        processed.add(symbol)
        
        for other_symbol in symbols:
            if other_symbol in processed or other_symbol == symbol:
                continue
            
            # Check correlation in both directions
            corr1 = correlations.get(symbol, {}).get(other_symbol, 0.0)
            corr2 = correlations.get(other_symbol, {}).get(symbol, 0.0)
            corr = max(abs(corr1), abs(corr2))
            
            if corr >= threshold:
                group.add(other_symbol)
                processed.add(other_symbol)
        
        if len(group) > 1:  # Only add groups with multiple symbols
            groups.append(group)
    
    return groups


def calculate_var(
    returns: List[float],
    confidence_level: float = 0.95,
    portfolio_value: float = 100000.0
) -> float:
    """
    Calculate Value at Risk (VaR) using historical simulation method.
    
    Args:
        returns: List of portfolio returns (as decimals, e.g., 0.05 for 5%)
        confidence_level: Confidence level (default: 0.95 for 95% VaR)
        portfolio_value: Current portfolio value
        
    Returns:
        VaR estimate in dollars (positive number representing potential loss)
    """
    if not returns or len(returns) < 10:
        return 0.0
    
    try:
        # Sort returns to find percentile
        sorted_returns = sorted(returns)
        
        # Calculate percentile index (1 - confidence_level)
        percentile = 1.0 - confidence_level
        index = int(len(sorted_returns) * percentile)
        index = max(0, min(index, len(sorted_returns) - 1))
        
        # Get return at this percentile (worst case)
        var_return = sorted_returns[index]
        
        # Convert to dollar amount (negative return means loss)
        var_dollars = abs(var_return) * portfolio_value
        
        return var_dollars
    except Exception:
        return 0.0
