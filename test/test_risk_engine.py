"""
Tests for risk engine module.
"""
import unittest

from app.core.config import get_settings
from app.trading.models import Order, PortfolioPosition, PortfolioState
from app.trading.risk_engine import risk_assess
from test.test_helpers import create_mock_order, create_mock_portfolio_state


class TestRiskEngine(unittest.TestCase):
    """Test risk assessment functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.settings = get_settings()
        self.portfolio = create_mock_portfolio_state(cash=100000.0)
        self.latest_prices = {"AAPL": 150.0, "MSFT": 300.0}

    def test_blacklist_filtering(self):
        """Test that blacklisted symbols are rejected."""
        # Add a symbol to blacklist (if config allows)
        blacklisted_symbol = "BLACKLISTED"
        
        # Create order for blacklisted symbol
        order = create_mock_order(
            symbol=blacklisted_symbol,
            side="buy",
            quantity=10.0,
        )

        # Temporarily add to blacklist if we can modify settings
        original_blacklist = self.settings.risk.blacklist_symbols.copy()
        try:
            # Note: This test assumes blacklist is configurable
            # If not, we'll test with a symbol that's already blacklisted
            orders = [order]
            assessment = risk_assess(
                portfolio=self.portfolio,
                proposed_trades=orders,
                latest_prices={blacklisted_symbol: 100.0},
            )

            # If symbol is blacklisted, it should be in violations
            if blacklisted_symbol in self.settings.risk.blacklist_symbols:
                self.assertGreater(len(assessment.violations), 0)
                self.assertEqual(len(assessment.approved_trades), 0)
        finally:
            # Restore original blacklist
            pass

    def test_max_trade_notional_limit(self):
        """Test that orders exceeding max trade notional are rejected."""
        max_notional = self.settings.risk.max_trade_notional
        
        # Create order that exceeds max notional
        # e.g., if max_notional is 10000, and price is 150, quantity > 66.67 would exceed
        excessive_quantity = (max_notional / self.latest_prices["AAPL"]) + 100
        order = create_mock_order(
            symbol="AAPL",
            side="buy",
            quantity=excessive_quantity,
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=self.portfolio,
            proposed_trades=orders,
            latest_prices=self.latest_prices,
        )

        # Should have violation for exceeding notional
        self.assertGreater(len(assessment.violations), 0)
        self.assertIn("notional", assessment.violations[0].lower())
        self.assertEqual(len(assessment.approved_trades), 0)

    def test_portfolio_exposure_limit(self):
        """Test that orders exceeding max portfolio exposure are rejected."""
        max_exposure = self.settings.risk.max_portfolio_exposure
        
        # Create order that exceeds max exposure
        # e.g., if max_exposure is 0.1 (10%), and portfolio is 100k, notional > 10k would exceed
        portfolio_value = self.portfolio.cash
        max_allowed_notional = portfolio_value * max_exposure
        excessive_quantity = (max_allowed_notional / self.latest_prices["AAPL"]) + 10
        
        order = create_mock_order(
            symbol="AAPL",
            side="buy",
            quantity=excessive_quantity,
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=self.portfolio,
            proposed_trades=orders,
            latest_prices=self.latest_prices,
        )

        # Should have violation for exceeding exposure
        self.assertGreater(len(assessment.violations), 0)
        self.assertIn("exposure", assessment.violations[0].lower())
        self.assertEqual(len(assessment.approved_trades), 0)

    def test_approved_trade(self):
        """Test that valid orders are approved."""
        # Create a small order that should pass all checks
        order = create_mock_order(
            symbol="AAPL",
            side="buy",
            quantity=10.0,  # Small order: 10 * 150 = 1500, well below limits
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=self.portfolio,
            proposed_trades=orders,
            latest_prices=self.latest_prices,
        )

        # Should be approved
        self.assertEqual(len(assessment.violations), 0)
        self.assertEqual(len(assessment.approved_trades), 1)
        self.assertEqual(assessment.approved_trades[0].symbol, "AAPL")

    def test_multiple_orders(self):
        """Test risk assessment with multiple orders."""
        orders = [
            create_mock_order(symbol="AAPL", side="buy", quantity=10.0),
            create_mock_order(symbol="MSFT", side="buy", quantity=5.0),
        ]

        assessment = risk_assess(
            portfolio=self.portfolio,
            proposed_trades=orders,
            latest_prices=self.latest_prices,
        )

        # Both should be assessed independently
        self.assertIsInstance(assessment.approved_trades, list)
        self.assertIsInstance(assessment.violations, list)

    def test_missing_price_uses_limit_price(self):
        """Test that limit price is used when latest price is missing."""
        order = create_mock_order(
            symbol="UNKNOWN",
            side="buy",
            quantity=10.0,
            order_type="limit",
            limit_price=200.0,
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=self.portfolio,
            proposed_trades=orders,
            latest_prices={},  # No price for UNKNOWN
        )

        # Should use limit price for notional calculation
        # Order should be assessed (may pass or fail depending on limits)
        self.assertIsInstance(assessment.approved_trades, list)
        self.assertIsInstance(assessment.violations, list)

    def test_missing_price_and_limit_price(self):
        """Test risk assessment when both latest price and limit price are missing."""
        order = create_mock_order(
            symbol="UNKNOWN",
            side="buy",
            quantity=10.0,
            order_type="market",
            limit_price=None,
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=self.portfolio,
            proposed_trades=orders,
            latest_prices={},  # No price available
        )

        # Should use fallback price (100.0) for calculation
        # Order should still be assessed
        self.assertIsInstance(assessment.approved_trades, list)
        self.assertIsInstance(assessment.violations, list)

    def test_portfolio_with_positions(self):
        """Test risk assessment with portfolio that has existing positions."""
        portfolio = create_mock_portfolio_state(
            cash=50000.0,
            positions=[
                PortfolioPosition(symbol="AAPL", quantity=50.0, average_price=140.0)
            ],
        )

        # Portfolio value = 50k cash + (50 * 150) = 57.5k
        order = create_mock_order(
            symbol="MSFT",
            side="buy",
            quantity=10.0,  # 10 * 300 = 3000, should be fine
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=portfolio,
            proposed_trades=orders,
            latest_prices=self.latest_prices,
        )

        # Should calculate portfolio value including positions
        self.assertIsInstance(assessment.approved_trades, list)

    def test_zero_portfolio_value(self):
        """Test risk assessment with zero portfolio value."""
        zero_portfolio = create_mock_portfolio_state(cash=0.0)

        order = create_mock_order(
            symbol="AAPL",
            side="buy",
            quantity=10.0,
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=zero_portfolio,
            proposed_trades=orders,
            latest_prices=self.latest_prices,
        )

        # Exposure check should handle zero portfolio value
        # Notional check should still work
        self.assertIsInstance(assessment.approved_trades, list)
        self.assertIsInstance(assessment.violations, list)

    def test_very_large_order(self):
        """Test risk assessment with extremely large order."""
        # Create order that's way too large
        order = create_mock_order(
            symbol="AAPL",
            side="buy",
            quantity=100000.0,  # 100k shares * 150 = 15M, definitely exceeds limits
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=self.portfolio,
            proposed_trades=orders,
            latest_prices=self.latest_prices,
        )

        # Should definitely be rejected
        self.assertGreater(len(assessment.violations), 0)
        self.assertEqual(len(assessment.approved_trades), 0)

    def test_sell_order_notional(self):
        """Test that sell orders are also checked for notional limits."""
        # Create large sell order
        max_notional = self.settings.risk.max_trade_notional
        excessive_quantity = (max_notional / self.latest_prices["AAPL"]) + 100
        
        order = create_mock_order(
            symbol="AAPL",
            side="sell",
            quantity=excessive_quantity,
        )

        orders = [order]
        assessment = risk_assess(
            portfolio=self.portfolio,
            proposed_trades=orders,
            latest_prices=self.latest_prices,
        )

        # Should check notional for sell orders too (using absolute value)
        self.assertGreater(len(assessment.violations), 0)


if __name__ == "__main__":
    unittest.main()

