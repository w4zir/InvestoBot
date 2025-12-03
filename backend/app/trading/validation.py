"""
Walk-forward validation module.

Provides data splitting, walk-forward window generation, and walk-forward backtest
execution for robust strategy evaluation.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.trading.backtester import run_backtest
from app.trading.models import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResult,
    ValidationConfig,
    WalkForwardResult,
)

logger = get_logger(__name__)


def split_data(
    ohlcv_data: Dict[str, List[Dict]],
    train_split: float = 0.7,
    validation_split: float = 0.15,
    holdout_split: float = 0.15,
) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Split OHLCV data into train/validation/holdout sets.

    Args:
        ohlcv_data: OHLCV data dictionary (symbol -> bars)
        train_split: Fraction of data for training (default 0.7)
        validation_split: Fraction of data for validation (default 0.15)
        holdout_split: Fraction of data for holdout (default 0.15)

    Returns:
        Dictionary with keys "train", "validation", "holdout", each containing
        OHLCV data in the same format as input
    """
    # Validate splits sum to 1.0
    total_split = train_split + validation_split + holdout_split
    if abs(total_split - 1.0) > 0.01:
        raise ValueError(f"Splits must sum to 1.0, got {total_split}")

    splits: Dict[str, Dict[str, List[Dict]]] = {
        "train": {},
        "validation": {},
        "holdout": {},
    }

    for symbol, bars in ohlcv_data.items():
        if not bars:
            continue

        # Sort bars by timestamp to ensure chronological order
        sorted_bars = sorted(bars, key=lambda b: b["timestamp"])

        total_bars = len(sorted_bars)
        train_end = int(total_bars * train_split)
        validation_end = int(total_bars * (train_split + validation_split))

        splits["train"][symbol] = sorted_bars[:train_end]
        splits["validation"][symbol] = sorted_bars[train_end:validation_end]
        splits["holdout"][symbol] = sorted_bars[validation_end:]

        logger.debug(
            f"Split {symbol}: train={len(splits['train'][symbol])}, "
            f"validation={len(splits['validation'][symbol])}, "
            f"holdout={len(splits['holdout'][symbol])}"
        )

    return splits


def create_walk_forward_windows(
    start_date: datetime,
    end_date: datetime,
    window_size: Optional[int] = None,
    expanding: bool = True,
    step_size: int = 1,
) -> List[Tuple[datetime, datetime, datetime, datetime]]:
    """
    Generate rolling windows for walk-forward analysis.

    Args:
        start_date: Start of overall date range
        end_date: End of overall date range
        window_size: Fixed window size in days (None for expanding windows)
        expanding: If True, use expanding windows; if False, use fixed-size rolling windows
        step_size: Number of days to step forward between windows

    Returns:
        List of (train_start, train_end, test_start, test_end) tuples
    """
    windows = []
    current_train_start = start_date
    current_test_start = start_date

    total_days = (end_date - start_date).days
    if total_days < 30:
        logger.warning(f"Date range is very short ({total_days} days), may not generate useful windows")

    # Determine initial training window size
    if window_size is None:
        # Use 70% of total range for initial training window
        initial_train_days = int(total_days * 0.7)
    else:
        initial_train_days = window_size

    # Minimum training window size
    min_train_days = 30
    if initial_train_days < min_train_days:
        initial_train_days = min_train_days

    # Test window size (use 15% of total range or minimum 10 days)
    test_window_days = max(int(total_days * 0.15), 10)

    while current_test_start < end_date:
        # Calculate training window
        if expanding:
            # Expanding window: train from start to test_start
            train_start = start_date
            train_end = current_test_start
        else:
            # Fixed-size rolling window
            train_start = current_test_start - timedelta(days=initial_train_days)
            train_end = current_test_start

        # Calculate test window
        test_start = current_test_start
        test_end = min(test_start + timedelta(days=test_window_days), end_date)

        # Ensure we have valid windows
        if train_end <= train_start:
            current_test_start += timedelta(days=step_size)
            continue

        if test_end <= test_start:
            break

        if (train_end - train_start).days < min_train_days:
            current_test_start += timedelta(days=step_size)
            continue

        windows.append((train_start, train_end, test_start, test_end))

        # Move to next window
        current_test_start += timedelta(days=step_size)

        # Stop if we've reached the end
        if test_end >= end_date:
            break

    logger.info(f"Generated {len(windows)} walk-forward windows")
    return windows


def _aggregate_metrics(results: List[BacktestResult]) -> BacktestMetrics:
    """Aggregate metrics across multiple backtest results."""
    if not results:
        return BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0)

    sharpe_values = [r.metrics.sharpe for r in results if r.metrics.sharpe is not None]
    max_dd_values = [r.metrics.max_drawdown for r in results if r.metrics.max_drawdown is not None]
    return_values = [r.metrics.total_return for r in results if r.metrics.total_return is not None]

    avg_sharpe = sum(sharpe_values) / len(sharpe_values) if sharpe_values else 0.0
    avg_max_dd = sum(max_dd_values) / len(max_dd_values) if max_dd_values else 0.0
    avg_return = sum(return_values) / len(return_values) if return_values else 0.0

    return BacktestMetrics(sharpe=avg_sharpe, max_drawdown=avg_max_dd, total_return=avg_return)


def run_walk_forward_backtest(
    request: BacktestRequest,
    ohlcv_data: Dict[str, List[Dict]],
    config: ValidationConfig,
) -> WalkForwardResult:
    """
    Run walk-forward backtest on a strategy.

    Args:
        request: BacktestRequest with strategy and costs
        ohlcv_data: Pre-loaded OHLCV data
        config: ValidationConfig with walk-forward settings

    Returns:
        WalkForwardResult with per-window and aggregate metrics
    """
    if not config.walk_forward:
        # If walk-forward is disabled, just run a single backtest
        result = run_backtest(request, ohlcv_data)
        return WalkForwardResult(
            windows=[result],
            aggregate_metrics=result.metrics,
            train_metrics=result.metrics,
            validation_metrics=result.metrics,
            holdout_metrics=None,
        )

    # Split data if splits are specified
    if config.train_split > 0 or config.validation_split > 0 or config.holdout_split > 0:
        splits = split_data(
            ohlcv_data,
            train_split=config.train_split,
            validation_split=config.validation_split,
            holdout_split=config.holdout_split,
        )

        # Run backtest on each split
        train_result = run_backtest(request, splits["train"])
        validation_result = run_backtest(request, splits["validation"])
        holdout_result = run_backtest(request, splits["holdout"]) if splits["holdout"] else None

        # Aggregate metrics
        all_results = [train_result, validation_result]
        if holdout_result:
            all_results.append(holdout_result)
        aggregate_metrics = _aggregate_metrics(all_results)

        return WalkForwardResult(
            windows=[train_result, validation_result],
            aggregate_metrics=aggregate_metrics,
            train_metrics=train_result.metrics,
            validation_metrics=validation_result.metrics,
            holdout_metrics=holdout_result.metrics if holdout_result else None,
        )

    # Walk-forward windows
    # Extract date range from data
    all_timestamps = []
    for symbol, bars in ohlcv_data.items():
        for bar in bars:
            timestamp = bar["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            all_timestamps.append(timestamp)

    if not all_timestamps:
        logger.error("No timestamps found in OHLCV data")
        result = run_backtest(request, ohlcv_data)
        return WalkForwardResult(
            windows=[result],
            aggregate_metrics=result.metrics,
            train_metrics=result.metrics,
            validation_metrics=result.metrics,
            holdout_metrics=None,
        )

    start_date = min(all_timestamps)
    end_date = max(all_timestamps)

    # Create walk-forward windows
    windows = create_walk_forward_windows(
        start_date,
        end_date,
        window_size=config.window_size,
        expanding=True,  # Default to expanding windows
    )

    if not windows:
        logger.warning("No walk-forward windows generated, falling back to single backtest")
        result = run_backtest(request, ohlcv_data)
        return WalkForwardResult(
            windows=[result],
            aggregate_metrics=result.metrics,
            train_metrics=result.metrics,
            validation_metrics=result.metrics,
            holdout_metrics=None,
        )

    # Run backtest on each window
    window_results: List[BacktestResult] = []
    for train_start, train_end, test_start, test_end in windows:
        # Filter data for training period
        train_data: Dict[str, List[Dict]] = {}
        for symbol, bars in ohlcv_data.items():
            train_bars = [
                bar
                for bar in bars
                if train_start <= bar["timestamp"] <= train_end
            ]
            if train_bars:
                train_data[symbol] = train_bars

        # Filter data for test period
        test_data: Dict[str, List[Dict]] = {}
        for symbol, bars in ohlcv_data.items():
            test_bars = [
                bar
                for bar in bars
                if test_start <= bar["timestamp"] <= test_end
            ]
            if test_bars:
                test_data[symbol] = test_bars

        # Run backtest on training period (for parameter optimization)
        # For now, we'll run on test period to evaluate performance
        if test_data:
            test_result = run_backtest(request, test_data)
            window_results.append(test_result)

    if not window_results:
        logger.error("No window results generated")
        result = run_backtest(request, ohlcv_data)
        return WalkForwardResult(
            windows=[result],
            aggregate_metrics=result.metrics,
            train_metrics=result.metrics,
            validation_metrics=result.metrics,
            holdout_metrics=None,
        )

    # Aggregate metrics across all windows
    aggregate_metrics = _aggregate_metrics(window_results)

    # Calculate train/validation metrics (use first window for train, last for validation)
    train_metrics = window_results[0].metrics if window_results else BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0)
    validation_metrics = window_results[-1].metrics if len(window_results) > 1 else train_metrics

    return WalkForwardResult(
        windows=window_results,
        aggregate_metrics=aggregate_metrics,
        train_metrics=train_metrics,
        validation_metrics=validation_metrics,
        holdout_metrics=None,
    )

