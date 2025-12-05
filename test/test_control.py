"""
Tests for control endpoints (kill switch, order cancellation, etc.).
"""
import unittest
from unittest.mock import MagicMock, patch

from app.routes.control import (
    cancel_all_orders,
    disable_kill_switch,
    enable_kill_switch,
    get_kill_switch_status,
    get_open_orders,
    get_scheduler_status,
    is_kill_switch_enabled,
)


class TestControl(unittest.TestCase):
    """Test control endpoint functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset kill switch state before each test
        disable_kill_switch()

    def test_enable_kill_switch(self):
        """Test enabling kill switch."""
        result = enable_kill_switch(reason="Test activation")
        
        self.assertEqual(result["status"], "enabled")
        self.assertEqual(result["reason"], "Test activation")
        self.assertIn("activated_at", result)
        self.assertTrue(is_kill_switch_enabled())

    def test_disable_kill_switch(self):
        """Test disabling kill switch."""
        # First enable it
        enable_kill_switch(reason="Test")
        
        # Then disable it
        result = disable_kill_switch()
        
        self.assertEqual(result["status"], "disabled")
        self.assertFalse(is_kill_switch_enabled())

    def test_get_kill_switch_status_enabled(self):
        """Test getting kill switch status when enabled."""
        enable_kill_switch(reason="Test")
        
        status = get_kill_switch_status()
        
        self.assertTrue(status["enabled"])
        self.assertEqual(status["reason"], "Test")
        self.assertIsNotNone(status["activated_at"])

    def test_get_kill_switch_status_disabled(self):
        """Test getting kill switch status when disabled."""
        status = get_kill_switch_status()
        
        self.assertFalse(status["enabled"])
        self.assertIsNone(status["reason"])
        self.assertIsNone(status["activated_at"])

    @patch('app.routes.control.get_broker')
    def test_cancel_all_orders_success(self, mock_get_broker):
        """Test successful cancellation of all orders."""
        # Mock broker
        mock_broker = MagicMock()
        mock_get_broker.return_value = mock_broker
        
        # Mock cancel_all_orders method
        mock_broker.cancel_all_orders.return_value = {
            "cancelled_count": 2,
            "total_orders": 2,
            "errors": [],
            "message": "Cancelled 2 of 2 open orders"
        }
        
        result = cancel_all_orders()
        
        self.assertEqual(result["cancelled_count"], 2)
        self.assertEqual(result["total_orders"], 2)
        self.assertEqual(len(result["errors"]), 0)

    @patch('app.routes.control.get_broker')
    def test_cancel_all_orders_no_orders(self, mock_get_broker):
        """Test cancellation when there are no open orders."""
        mock_broker = MagicMock()
        mock_get_broker.return_value = mock_broker
        
        # Mock cancel_all_orders method for no orders
        mock_broker.cancel_all_orders.return_value = {
            "cancelled_count": 0,
            "total_orders": 0,
            "errors": [],
            "message": "No open orders to cancel"
        }
        
        result = cancel_all_orders()
        
        self.assertEqual(result["cancelled_count"], 0)
        self.assertEqual(result["total_orders"], 0)

    @patch('app.routes.control.get_broker')
    def test_cancel_all_orders_partial_failure(self, mock_get_broker):
        """Test cancellation when some orders fail to cancel."""
        mock_broker = MagicMock()
        mock_get_broker.return_value = mock_broker
        
        # Mock cancel_all_orders method with partial failure
        mock_broker.cancel_all_orders.return_value = {
            "cancelled_count": 1,
            "total_orders": 2,
            "errors": ["Failed to cancel order order2: Error message"],
            "message": "Cancelled 1 of 2 open orders"
        }
        
        result = cancel_all_orders()
        
        # Should have cancelled at least one, with errors
        self.assertGreater(result["cancelled_count"], 0)
        self.assertGreater(len(result["errors"]), 0)

    @patch('app.routes.control.get_broker')
    def test_get_open_orders(self, mock_get_broker):
        """Test getting open orders."""
        mock_broker = MagicMock()
        mock_get_broker.return_value = mock_broker
        
        mock_orders = [
            {"id": "order1", "symbol": "AAPL", "side": "buy", "qty": 10},
        ]
        
        # Mock get_all_orders method
        mock_broker.get_all_orders.return_value = mock_orders
        
        result = get_open_orders()
        
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["orders"]), 1)

    @patch('app.routes.control.get_active_runs')
    def test_get_scheduler_status(self, mock_get_active_runs):
        """Test getting scheduler status."""
        mock_get_active_runs.return_value = {
            "run_1": "2024-01-01T00:00:00",
            "run_2": "2024-01-01T01:00:00",
        }
        
        result = get_scheduler_status()
        
        self.assertEqual(result["active_run_count"], 2)
        self.assertIn("run_1", result["active_runs"])
        self.assertIn("run_2", result["active_runs"])
        self.assertIn("kill_switch_enabled", result)

    def test_is_kill_switch_enabled_function(self):
        """Test the is_kill_switch_enabled helper function."""
        # Initially disabled
        self.assertFalse(is_kill_switch_enabled())
        
        # Enable it
        enable_kill_switch()
        self.assertTrue(is_kill_switch_enabled())
        
        # Disable it
        disable_kill_switch()
        self.assertFalse(is_kill_switch_enabled())


if __name__ == "__main__":
    unittest.main()

