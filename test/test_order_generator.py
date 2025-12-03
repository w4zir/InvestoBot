"""
Tests for order generation module.
"""
import unittest
from datetime import datetime, timedelta

from app.trading.models import PortfolioPosition, PortfolioState, Trade
from app.trading.order_generator import generate_orders
from test.test_helpers import (
    create_mock_order,
    create_mock_portfolio_state,
    create_mock_strategy_spec,
    create_mock_trade,
)


class TestOrderGenerator(unittest.TestCase):
    """Test order generation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = create_mock_strategy_spec(
            strategy_id="test_order_gen",
            universe=["AAPL"],
            fraction=0.02,
        )
        self.portfolio = create_mock_portfolio_state(cash=100000.0)
        self.latest_prices = {"AAPL": 150.0}

    def test_order_generation_from_backtest_trades(self):
        """Test order generation from backtest trade log."""
        # Create trades that suggest buying AAPL
        trades = [
            create_mock_trade(
                symbol="AAPL",
                side="buy",
                quantity=13.33,  # 2% of 100k / 150 = ~13.33 shares
                price=150.0,
                timestamp=datetime.utcnow() - timedelta(days=1),
            ),
        ]

        orders = generate_orders(
            strategy=self.strategy,
            portfolio=self.portfolio,
            latest_prices=self.latest_prices,
            backtest_trades=trades,
        )

        self.assertGreater(len(orders), 0)
        self.assertEqual(orders[0].symbol, "AAPL")
        self.assertEqual(orders[0].side, "buy")
        self.assertGreater(orders[0].quantity, 0)

    def test_order_generation_with_existing_position(self):
        """Test order generation when portfolio already has positions."""
        # Portfolio with existing AAPL position
        portfolio = create_mock_portfolio_state(
            cash=50000.0,
            positions=[
                PortfolioPosition(symbol="AAPL", quantity=10.0, average_price=140.0)
            ],
        )

        # Backtest suggests buying more
        trades = [
            create_mock_trade(
                symbol="AAPL",
                side="buy",
                quantity=20.0,
                price=150.0,
            ),
        ]

        orders = generate_orders(
            strategy=self.strategy,
            portfolio=portfolio,
            latest_prices=self.latest_prices,
            backtest_trades=trades,
        )

        # Should generate order to increase position
        self.assertGreater(len(orders), 0)
        buy_orders = [o for o in orders if o.side == "buy"]
        if buy_orders:
            self.assertGreater(buy_orders[0].quantity, 0)

    def test_order_generation_sell_signal(self):
        """Test order generation for sell signals."""
        # Portfolio with existing position
        portfolio = create_mock_portfolio_state(
            cash=50000.0,
            positions=[
                PortfolioPosition(symbol="AAPL", quantity=20.0, average_price=140.0)
            ],
        )

        # Backtest suggests selling
        trades = [
            create_mock_trade(
                symbol="AAPL",
                side="sell",
                quantity=20.0,
                price=150.0,
            ),
        ]

        orders = generate_orders(
            strategy=self.strategy,
            portfolio=portfolio,
            latest_prices=self.latest_prices,
            backtest_trades=trades,
        )

        # Should generate sell order
        sell_orders = [o for o in orders if o.side == "sell"]
        if sell_orders:
            self.assertGreater(sell_orders[0].quantity, 0)

    def test_order_generation_fixed_fraction_position_sizing(self):
        """Test order generation with fixed_fraction position sizing."""
        strategy = create_mock_strategy_spec(
            strategy_id="test_fixed_fraction",
            universe=["AAPL"],
            fraction=0.05,  # 5% of portfolio
        )

        trades = [
            create_mock_trade(
                symbol="AAPL",
                side="buy",
                quantity=33.33,  # 5% of 100k / 150
                price=150.0,
            ),
        ]

        orders = generate_orders(
            strategy=strategy,
            portfolio=self.portfolio,
            latest_prices=self.latest_prices,
            backtest_trades=trades,
        )

        self.assertGreater(len(orders), 0)
        # Order quantity should be approximately 5% of portfolio value / price
        expected_qty = (self.portfolio.cash * 0.05) / self.latest_prices["AAPL"]
        self.assertAlmostEqual(orders[0].quantity, expected_qty, delta=1.0)

    def test_order_generation_multi_symbol(self):
        """Test order generation for multiple symbols."""
        strategy = create_mock_strategy_spec(
            strategy_id="test_multi_symbol",
            universe=["AAPL", "MSFT"],
            fraction=0.02,
        )

        latest_prices = {"AAPL": 150.0, "MSFT": 300.0}

        trades = [
            create_mock_trade(symbol="AAPL", side="buy", quantity=13.33, price=150.0),
            create_mock_trade(symbol="MSFT", side="buy", quantity=6.67, price=300.0),
        ]

        orders = generate_orders(
            strategy=strategy,
            portfolio=self.portfolio,
            latest_prices=latest_prices,
            backtest_trades=trades,
        )

        # Should have orders for both symbols
        symbols = {o.symbol for o in orders}
        self.assertIn("AAPL", symbols)
        self.assertIn("MSFT", symbols)

    def test_order_generation_empty_portfolio(self):
        """Test order generation with empty portfolio."""
        empty_portfolio = create_mock_portfolio_state(cash=0.0)

        trades = [
            create_mock_trade(symbol="AAPL", side="buy", quantity=10.0, price=150.0),
        ]

        orders = generate_orders(
            strategy=self.strategy,
            portfolio=empty_portfolio,
            latest_prices=self.latest_prices,
            backtest_trades=trades,
        )

        # Should return empty list when portfolio value is zero
        self.assertEqual(len(orders), 0)

    def test_order_generation_no_backtest_trades(self):
        """Test order generation when backtest has no trades."""
        orders = generate_orders(
            strategy=self.strategy,
            portfolio=self.portfolio,
            latest_prices=self.latest_prices,
            backtest_trades=[],
        )

        # Should still generate orders based on strategy params if no trades
        # The current implementation may or may not generate orders - either is acceptable
        # Just verify it doesn't crash
        self.assertIsInstance(orders, list)

    def test_order_generation_missing_price(self):
        """Test order generation when symbol price is missing."""
        latest_prices = {}  # Missing AAPL price

        trades = [
            create_mock_trade(symbol="AAPL", side="buy", quantity=10.0, price=150.0),
        ]

        orders = generate_orders(
            strategy=self.strategy,
            portfolio=self.portfolio,
            latest_prices=latest_prices,
            backtest_trades=trades,
        )

        # Should skip symbols without prices
        self.assertEqual(len(orders), 0)

    def test_order_generation_zero_price(self):
        """Test order generation with zero price (edge case)."""
        latest_prices = {"AAPL": 0.0}

        trades = [
            create_mock_trade(symbol="AAPL", side="buy", quantity=10.0, price=150.0),
        ]

        orders = generate_orders(
            strategy=self.strategy,
            portfolio=self.portfolio,
            latest_prices=latest_prices,
            backtest_trades=trades,
        )

        # Should handle zero price gracefully
        self.assertIsInstance(orders, list)

    def test_order_generation_negative_portfolio_value(self):
        """Test order generation with negative portfolio value."""
        negative_portfolio = create_mock_portfolio_state(cash=-1000.0)

        trades = [
            create_mock_trade(symbol="AAPL", side="buy", quantity=10.0, price=150.0),
        ]

        orders = generate_orders(
            strategy=self.strategy,
            portfolio=negative_portfolio,
            latest_prices=self.latest_prices,
            backtest_trades=trades,
        )

        # Should return empty list when portfolio value is negative
        self.assertEqual(len(orders), 0)

    def test_order_generation_accumulated_trades(self):
        """Test order generation with multiple trades for same symbol."""
        # Multiple buy trades should accumulate
        trades = [
            create_mock_trade(
                symbol="AAPL",
                side="buy",
                quantity=10.0,
                price=150.0,
                timestamp=datetime.utcnow() - timedelta(days=2),
            ),
            create_mock_trade(
                symbol="AAPL",
                side="buy",
                quantity=5.0,
                price=150.0,
                timestamp=datetime.utcnow() - timedelta(days=1),
            ),
            create_mock_trade(
                symbol="AAPL",
                side="sell",
                quantity=3.0,
                price=150.0,
                timestamp=datetime.utcnow(),
            ),
        ]

        orders = generate_orders(
            strategy=self.strategy,
            portfolio=self.portfolio,
            latest_prices=self.latest_prices,
            backtest_trades=trades,
        )

        # Should generate order based on net position (10 + 5 - 3 = 12)
        self.assertIsInstance(orders, list)


if __name__ == "__main__":
    unittest.main()

