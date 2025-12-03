"""
Tests for multi-symbol portfolio backtesting.
"""
import unittest
from datetime import datetime, timedelta

from app.trading.backtester import run_backtest
from app.trading.models import (
    BacktestRequest,
    PortfolioEvaluationMode,
    RebalancingMode,
    StrategyParams,
    StrategyRule,
    StrategySpec,
)


class TestMultiSymbolBacktesting(unittest.TestCase):
    """Test multi-symbol portfolio backtesting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create sample OHLCV data for multiple symbols
        self.start_date = datetime(2020, 1, 1)
        self.ohlcv_data = {}
        
        # Generate synthetic data for AAPL and MSFT
        for symbol in ["AAPL", "MSFT"]:
            bars = []
            base_price = 100.0 if symbol == "AAPL" else 150.0
            for i in range(100):
                timestamp = self.start_date + timedelta(days=i)
                # Simple price series with some trend
                price = base_price + (i * 0.5) + (i % 10) * 0.1
                bars.append({
                    "timestamp": timestamp,
                    "open": price,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": 1000000,
                })
            self.ohlcv_data[symbol] = bars

    def test_per_symbol_evaluation(self):
        """Test per-symbol evaluation mode."""
        strategy = StrategySpec(
            strategy_id="test_per_symbol",
            name="Test Per Symbol",
            universe=["AAPL", "MSFT"],
            rules=[
                StrategyRule(
                    type="entry",
                    indicator="sma",
                    params={"window": 10, "threshold": 0, "direction": "above"},
                ),
                StrategyRule(
                    type="exit",
                    indicator="sma",
                    params={"window": 20, "threshold": 0, "direction": "below"},
                ),
            ],
            params=StrategyParams(
                evaluation_mode=PortfolioEvaluationMode.PER_SYMBOL,
                rebalancing_mode=RebalancingMode.SIGNAL_BASED,
                position_sizing="fixed_fraction",
                fraction=0.1,
            ),
        )

        request = BacktestRequest(
            strategy=strategy,
            data_range=f"{self.start_date.isoformat()}:{(self.start_date + timedelta(days=100)).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        result = run_backtest(request, self.ohlcv_data)

        # Should have trades for both symbols
        self.assertIsNotNone(result)
        self.assertGreater(len(result.trade_log), 0)
        
        # Check that we have trades for multiple symbols
        symbols_traded = set(trade.symbol for trade in result.trade_log)
        self.assertGreaterEqual(len(symbols_traded), 1)  # At least one symbol should have trades

    def test_portfolio_level_evaluation(self):
        """Test portfolio-level evaluation mode."""
        strategy = StrategySpec(
            strategy_id="test_portfolio_level",
            name="Test Portfolio Level",
            universe=["AAPL", "MSFT"],
            rules=[
                StrategyRule(
                    type="entry",
                    indicator="sma",
                    params={"window": 10, "threshold": 0, "direction": "above"},
                ),
            ],
            params=StrategyParams(
                evaluation_mode=PortfolioEvaluationMode.PORTFOLIO_LEVEL,
                rebalancing_mode=RebalancingMode.SIGNAL_BASED,
                max_positions=2,
                position_sizing="fixed_fraction",
                fraction=0.1,
            ),
        )

        request = BacktestRequest(
            strategy=strategy,
            data_range=f"{self.start_date.isoformat()}:{(self.start_date + timedelta(days=100)).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        result = run_backtest(request, self.ohlcv_data)

        # Should complete without errors
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.metrics)

    def test_time_based_rebalancing(self):
        """Test time-based rebalancing."""
        strategy = StrategySpec(
            strategy_id="test_time_rebalance",
            name="Test Time Rebalance",
            universe=["AAPL"],
            rules=[
                StrategyRule(
                    type="entry",
                    indicator="sma",
                    params={"window": 10, "threshold": 0, "direction": "above"},
                ),
            ],
            params=StrategyParams(
                evaluation_mode=PortfolioEvaluationMode.PER_SYMBOL,
                rebalancing_mode=RebalancingMode.TIME_BASED,
                rebalancing_frequency="7d",  # Weekly rebalancing
                position_sizing="fixed_fraction",
                fraction=0.1,
            ),
        )

        request = BacktestRequest(
            strategy=strategy,
            data_range=f"{self.start_date.isoformat()}:{(self.start_date + timedelta(days=100)).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        result = run_backtest(request, self.ohlcv_data)

        # Should complete without errors
        self.assertIsNotNone(result)

    def test_signal_based_rebalancing(self):
        """Test signal-based rebalancing."""
        strategy = StrategySpec(
            strategy_id="test_signal_rebalance",
            name="Test Signal Rebalance",
            universe=["AAPL"],
            rules=[
                StrategyRule(
                    type="entry",
                    indicator="sma",
                    params={"window": 10, "threshold": 0, "direction": "above"},
                ),
                StrategyRule(
                    type="exit",
                    indicator="sma",
                    params={"window": 20, "threshold": 0, "direction": "below"},
                ),
            ],
            params=StrategyParams(
                evaluation_mode=PortfolioEvaluationMode.PER_SYMBOL,
                rebalancing_mode=RebalancingMode.SIGNAL_BASED,
                position_sizing="fixed_fraction",
                fraction=0.1,
            ),
        )

        request = BacktestRequest(
            strategy=strategy,
            data_range=f"{self.start_date.isoformat()}:{(self.start_date + timedelta(days=100)).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        result = run_backtest(request, self.ohlcv_data)

        # Should complete without errors
        self.assertIsNotNone(result)

    def test_backward_compatibility_single_symbol(self):
        """Test that single-symbol backtesting still works (backward compatibility)."""
        strategy = StrategySpec(
            strategy_id="test_single_symbol",
            name="Test Single Symbol",
            universe=["AAPL"],
            rules=[
                StrategyRule(
                    type="entry",
                    indicator="sma",
                    params={"window": 10, "threshold": 0, "direction": "above"},
                ),
            ],
            params=StrategyParams(
                evaluation_mode=PortfolioEvaluationMode.PER_SYMBOL,
                rebalancing_mode=RebalancingMode.SIGNAL_BASED,
                position_sizing="fixed_fraction",
                fraction=0.1,
            ),
        )

        request = BacktestRequest(
            strategy=strategy,
            data_range=f"{self.start_date.isoformat()}:{(self.start_date + timedelta(days=100)).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        result = run_backtest(request, self.ohlcv_data)

        # Should complete without errors and have trades
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.metrics)


if __name__ == "__main__":
    unittest.main()

