"""
Technical indicators for strategy evaluation.
"""
from typing import Dict, List

import numpy as np


def sma(prices: List[float], window: int) -> List[float]:
    """
    Simple Moving Average.

    Args:
        prices: List of closing prices
        window: Window size for moving average

    Returns:
        List of SMA values (same length as prices, with NaN for first window-1 values)
    """
    if len(prices) < window:
        return [float("nan")] * len(prices)

    result = []
    for i in range(len(prices)):
        if i < window - 1:
            result.append(float("nan"))
        else:
            window_prices = prices[i - window + 1 : i + 1]
            result.append(sum(window_prices) / window)
    return result


def ema(prices: List[float], window: int) -> List[float]:
    """
    Exponential Moving Average.

    Args:
        prices: List of closing prices
        window: Window size for EMA

    Returns:
        List of EMA values
    """
    if len(prices) < window:
        return [float("nan")] * len(prices)

    multiplier = 2.0 / (window + 1)
    result = [float("nan")] * (window - 1)
    result.append(sum(prices[:window]) / window)  # First EMA value is SMA

    for i in range(window, len(prices)):
        ema_value = (prices[i] - result[-1]) * multiplier + result[-1]
        result.append(ema_value)

    return result


def calculate_returns(prices: List[float]) -> List[float]:
    """
    Calculate daily returns from price series.

    Args:
        prices: List of closing prices

    Returns:
        List of returns (first value is NaN)
    """
    if len(prices) < 2:
        return [float("nan")] * len(prices)

    returns = [float("nan")]
    for i in range(1, len(prices)):
        if prices[i - 1] != 0:
            ret = (prices[i] - prices[i - 1]) / prices[i - 1]
            returns.append(ret)
        else:
            returns.append(float("nan"))
    return returns


def zscore(values: List[float], window: int) -> List[float]:
    """
    Calculate Z-score (standardized values).

    Args:
        values: List of values
        window: Window size for rolling mean/std

    Returns:
        List of Z-scores
    """
    if len(values) < window:
        return [float("nan")] * len(values)

    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(float("nan"))
        else:
            window_values = values[i - window + 1 : i + 1]
            mean = sum(window_values) / len(window_values)
            variance = sum((x - mean) ** 2 for x in window_values) / len(window_values)
            std = variance ** 0.5
            if std > 0:
                z = (values[i] - mean) / std
                result.append(z)
            else:
                result.append(0.0)
    return result


def evaluate_indicator(indicator_name: str, prices: List[float], params: Dict) -> List[float]:
    """
    Evaluate a technical indicator by name.

    Args:
        indicator_name: Name of indicator (e.g., "sma", "ema", "zscore")
        prices: List of closing prices
        params: Parameters for the indicator

    Returns:
        List of indicator values
    """
    indicator_name_lower = indicator_name.lower()

    if indicator_name_lower == "sma":
        window = params.get("window", 20)
        return sma(prices, window)
    elif indicator_name_lower == "ema":
        window = params.get("window", 20)
        return ema(prices, window)
    elif indicator_name_lower == "zscore":
        window = params.get("window", 20)
        returns = calculate_returns(prices)
        return zscore(returns, window)
    else:
        raise ValueError(f"Unknown indicator: {indicator_name}")

