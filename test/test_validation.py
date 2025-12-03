"""
Tests for walk-forward validation.
"""
import unittest
from datetime import datetime, timedelta

from app.trading.models import (
    BacktestRequest,
    StrategyParams,
    StrategyRule,
    StrategySpec,
    ValidationConfig,
)
from app.trading.validation import (
    create_walk_forward_windows,
    run_walk_forward_backtest,
    split_data,
)


class TestValidation(unittest.TestCase):
    """Test walk-forward validation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.start_date = datetime(2020, 1, 1)
        self.ohlcv_data = {}
        
        # Generate synthetic data
        for symbol in ["AAPL"]:
            bars = []
            base_price = 100.0
            for i in range(200):  # 200 days of data
                timestamp = self.start_date + timedelta(days=i)
                price = base_price + (i * 0.5)
                bars.append({
                    "timestamp": timestamp,
                    "open": price,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": 1000000,
                })
            self.ohlcv_data[symbol] = bars

    def test_split_data_70_15_15(self):
        """Test data splitting with 70/15/15 split."""
        splits = split_data(self.ohlcv_data, train_split=0.7, validation_split=0.15, holdout_split=0.15)

        self.assertIn("train", splits)
        self.assertIn("validation", splits)
        self.assertIn("holdout", splits)

        # Check that splits are approximately correct
        total_bars = len(self.ohlcv_data["AAPL"])
        train_bars = len(splits["train"]["AAPL"])
        validation_bars = len(splits["validation"]["AAPL"])
        holdout_bars = len(splits["holdout"]["AAPL"])

        self.assertAlmostEqual(train_bars / total_bars, 0.7, delta=0.05)
        self.assertAlmostEqual(validation_bars / total_bars, 0.15, delta=0.05)
        self.assertAlmostEqual(holdout_bars / total_bars, 0.15, delta=0.05)

    def test_split_data_custom_ratios(self):
        """Test data splitting with custom ratios."""
        splits = split_data(self.ohlcv_data, train_split=0.8, validation_split=0.1, holdout_split=0.1)

        total_bars = len(self.ohlcv_data["AAPL"])
        train_bars = len(splits["train"]["AAPL"])

        self.assertAlmostEqual(train_bars / total_bars, 0.8, delta=0.05)

    def test_create_walk_forward_windows(self):
        """Test walk-forward window generation."""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 12, 31)

        windows = create_walk_forward_windows(start_date, end_date, expanding=True)

        self.assertGreater(len(windows), 0)

        # Check window structure
        for train_start, train_end, test_start, test_end in windows:
            self.assertLess(train_start, train_end)
            self.assertLess(train_end, test_start)
            self.assertLess(test_start, test_end)
            self.assertLessEqual(test_end, end_date)

    def test_create_fixed_size_windows(self):
        """Test fixed-size walk-forward windows."""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 12, 31)

        windows = create_walk_forward_windows(
            start_date, end_date, window_size=60, expanding=False
        )

        self.assertGreater(len(windows), 0)

        # Check that windows are approximately the right size
        for train_start, train_end, test_start, test_end in windows:
            train_days = (train_end - train_start).days
            self.assertGreaterEqual(train_days, 30)  # At least minimum

    def test_run_walk_forward_backtest_with_splits(self):
        """Test walk-forward backtest with train/validation/holdout splits."""
        strategy = StrategySpec(
            strategy_id="test_wf",
            name="Test Walk Forward",
            universe=["AAPL"],
            rules=[
                StrategyRule(
                    type="entry",
                    indicator="sma",
                    params={"window": 10, "threshold": 0, "direction": "above"},
                ),
            ],
            params=StrategyParams(
                position_sizing="fixed_fraction",
                fraction=0.1,
            ),
        )

        request = BacktestRequest(
            strategy=strategy,
            data_range=f"{self.start_date.isoformat()}:{(self.start_date + timedelta(days=200)).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        config = ValidationConfig(
            train_split=0.7,
            validation_split=0.15,
            holdout_split=0.15,
            walk_forward=False,
        )

        result = run_walk_forward_backtest(request, self.ohlcv_data, config)

        self.assertIsNotNone(result)
        self.assertIsNotNone(result.train_metrics)
        self.assertIsNotNone(result.validation_metrics)
        self.assertIsNotNone(result.holdout_metrics)
        self.assertGreaterEqual(len(result.windows), 2)

    def test_run_walk_forward_backtest_disabled(self):
        """Test walk-forward backtest when disabled."""
        strategy = StrategySpec(
            strategy_id="test_wf_disabled",
            name="Test Walk Forward Disabled",
            universe=["AAPL"],
            rules=[
                StrategyRule(
                    type="entry",
                    indicator="sma",
                    params={"window": 10, "threshold": 0, "direction": "above"},
                ),
            ],
            params=StrategyParams(
                position_sizing="fixed_fraction",
                fraction=0.1,
            ),
        )

        request = BacktestRequest(
            strategy=strategy,
            data_range=f"{self.start_date.isoformat()}:{(self.start_date + timedelta(days=200)).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        config = ValidationConfig(
            walk_forward=False,
            train_split=0.0,
            validation_split=0.0,
            holdout_split=0.0,
        )

        result = run_walk_forward_backtest(request, self.ohlcv_data, config)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(len(result.windows), 1)

    def test_create_walk_forward_windows_expanding(self):
        """Test expanding walk-forward windows."""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 6, 30)  # 6 months

        windows = create_walk_forward_windows(start_date, end_date, expanding=True)

        self.assertGreater(len(windows), 0)

        # In expanding windows, each train period should be larger than the previous
        if len(windows) > 1:
            first_train_days = (windows[0][1] - windows[0][0]).days
            second_train_days = (windows[1][1] - windows[1][0]).days
            self.assertLessEqual(first_train_days, second_train_days)

    def test_create_walk_forward_windows_fixed_size(self):
        """Test fixed-size walk-forward windows."""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 12, 31)

        windows = create_walk_forward_windows(
            start_date, end_date, window_size=60, expanding=False
        )

        self.assertGreater(len(windows), 0)

        # In fixed-size windows, train periods should be approximately the same size
        if len(windows) > 1:
            first_train_days = (windows[0][1] - windows[0][0]).days
            second_train_days = (windows[1][1] - windows[1][0]).days
            # Allow some variance due to date boundaries
            self.assertAlmostEqual(first_train_days, second_train_days, delta=5)

    def test_create_walk_forward_windows_step_size(self):
        """Test walk-forward windows with custom step size."""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 12, 31)

        # Test with larger step size (monthly steps)
        windows_large_step = create_walk_forward_windows(
            start_date, end_date, window_size=60, expanding=False, step_size=30
        )

        # Test with smaller step size (weekly steps)
        windows_small_step = create_walk_forward_windows(
            start_date, end_date, window_size=60, expanding=False, step_size=7
        )

        # Larger step size should produce fewer windows
        self.assertGreater(len(windows_small_step), len(windows_large_step))

    def test_split_data_insufficient_data(self):
        """Test data splitting with insufficient data."""
        # Create minimal data (only 10 bars)
        minimal_data = {}
        for symbol in ["AAPL"]:
            bars = []
            for i in range(10):
                timestamp = self.start_date + timedelta(days=i)
                bars.append({
                    "timestamp": timestamp,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 1000000,
                })
            minimal_data[symbol] = bars

        # Should still work, but splits will be small
        splits = split_data(minimal_data, train_split=0.7, validation_split=0.15, holdout_split=0.15)

        self.assertIn("train", splits)
        self.assertIn("validation", splits)
        self.assertIn("holdout", splits)
        # Each split should have at least 1 bar
        self.assertGreater(len(splits["train"]["AAPL"]), 0)

    def test_split_data_empty_input(self):
        """Test data splitting with empty input."""
        empty_data = {}

        # Should handle gracefully
        splits = split_data(empty_data, train_split=0.7, validation_split=0.15, holdout_split=0.15)

        self.assertIn("train", splits)
        self.assertIn("validation", splits)
        self.assertIn("holdout", splits)

    def test_split_data_invalid_splits(self):
        """Test data splitting with invalid split ratios."""
        # Splits that don't sum to 1.0 should raise ValueError
        with self.assertRaises(ValueError):
            split_data(self.ohlcv_data, train_split=0.8, validation_split=0.2, holdout_split=0.2)

    def test_create_walk_forward_windows_short_period(self):
        """Test walk-forward windows with very short date range."""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 31)  # Only 30 days

        windows = create_walk_forward_windows(start_date, end_date, expanding=True)

        # Should still generate at least one window if possible
        # May return empty list if period is too short
        self.assertIsInstance(windows, list)

    def test_create_walk_forward_windows_reversed_dates(self):
        """Test walk-forward windows with reversed dates (should handle gracefully)."""
        start_date = datetime(2020, 12, 31)
        end_date = datetime(2020, 1, 1)  # Reversed

        # Should handle gracefully (may return empty list or raise error)
        # The implementation should validate dates
        windows = create_walk_forward_windows(start_date, end_date, expanding=True)

        # Should return empty list or handle error
        self.assertIsInstance(windows, list)

    def test_run_walk_forward_backtest_with_walk_forward_enabled(self):
        """Test walk-forward backtest with walk_forward=True."""
        strategy = StrategySpec(
            strategy_id="test_wf_enabled",
            name="Test Walk Forward Enabled",
            universe=["AAPL"],
            rules=[
                StrategyRule(
                    type="entry",
                    indicator="sma",
                    params={"window": 10, "threshold": 0, "direction": "above"},
                ),
            ],
            params=StrategyParams(
                position_sizing="fixed_fraction",
                fraction=0.1,
            ),
        )

        request = BacktestRequest(
            strategy=strategy,
            data_range=f"{self.start_date.isoformat()}:{(self.start_date + timedelta(days=200)).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        config = ValidationConfig(
            walk_forward=True,
            window_size=60,  # 60-day windows
        )

        result = run_walk_forward_backtest(request, self.ohlcv_data, config)

        self.assertIsNotNone(result)
        # Should have multiple windows when walk_forward is enabled
        self.assertGreater(len(result.windows), 1)
        self.assertIsNotNone(result.aggregate_metrics)


if __name__ == "__main__":
    unittest.main()

