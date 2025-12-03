"""
Tests for persistence service module.
"""
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.trading.models import (
    BacktestMetrics,
    BacktestResult,
    CandidateResult,
    RiskAssessment,
    StrategyRunResponse,
)
from app.trading.persistence import PersistenceService
from test.test_helpers import (
    create_mock_backtest_result,
    create_mock_strategy_spec,
)


class TestPersistenceService(unittest.TestCase):
    """Test persistence service functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = create_mock_strategy_spec(strategy_id="test_persist")
        self.backtest_result = create_mock_backtest_result(
            strategy=self.strategy,
            sharpe=1.0,
            max_drawdown=0.1,
            total_return=0.15,
        )

    @patch('app.trading.persistence.get_supabase_client')
    def test_initialization_with_client(self, mock_get_client):
        """Test persistence service initialization with Supabase client."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        service = PersistenceService()
        
        self.assertIsNotNone(service.client)
        self.assertEqual(service.client, mock_client)

    @patch('app.trading.persistence.get_supabase_client')
    def test_initialization_without_client(self, mock_get_client):
        """Test persistence service initialization without Supabase client."""
        mock_get_client.return_value = None
        
        service = PersistenceService()
        
        self.assertIsNone(service.client)

    @patch('app.trading.persistence.get_supabase_client')
    def test_save_strategy_run_success(self, mock_get_client):
        """Test successful strategy run persistence."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock table operations
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = None
        mock_table.insert.return_value.execute.return_value = None
        
        service = PersistenceService()
        
        candidate = CandidateResult(
            strategy=self.strategy,
            backtest=self.backtest_result,
            risk=RiskAssessment(approved_trades=[], violations=[]),
            execution_fills=[],
            execution_error=None,
        )
        
        response = StrategyRunResponse(
            run_id="test_run",
            mission="test mission",
            candidates=[candidate],
            created_at=datetime.utcnow(),
        )
        
        result = service.save_strategy_run(response, context={"universe": ["AAPL"]})
        
        self.assertTrue(result)
        # Verify table operations were called
        mock_client.table.assert_called()

    @patch('app.trading.persistence.get_supabase_client')
    def test_save_strategy_run_no_client(self, mock_get_client):
        """Test persistence when Supabase client is unavailable."""
        mock_get_client.return_value = None
        
        service = PersistenceService()
        
        response = StrategyRunResponse(
            run_id="test_run",
            mission="test mission",
            candidates=[],
            created_at=datetime.utcnow(),
        )
        
        result = service.save_strategy_run(response)
        
        # Should return False but not raise exception
        self.assertFalse(result)

    @patch('app.trading.persistence.get_supabase_client')
    def test_save_strategy_run_with_error(self, mock_get_client):
        """Test persistence handles errors gracefully."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock table to raise exception
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.side_effect = Exception("Database error")
        
        service = PersistenceService()
        
        response = StrategyRunResponse(
            run_id="test_run",
            mission="test mission",
            candidates=[],
            created_at=datetime.utcnow(),
        )
        
        # Should return False but not raise exception
        result = service.save_strategy_run(response)
        self.assertFalse(result)

    @patch('app.trading.persistence.get_supabase_client')
    def test_save_strategy_run_with_execution_results(self, mock_get_client):
        """Test persistence includes execution results."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = None
        mock_table.insert.return_value.execute.return_value = None
        
        service = PersistenceService()
        
        from app.trading.models import Fill
        
        fills = [
            Fill(
                order_id="order1",
                symbol="AAPL",
                side="buy",
                quantity=10.0,
                price=150.0,
                timestamp=datetime.utcnow(),
            )
        ]
        
        candidate = CandidateResult(
            strategy=self.strategy,
            backtest=self.backtest_result,
            risk=RiskAssessment(approved_trades=[], violations=[]),
            execution_fills=fills,
            execution_error=None,
        )
        
        response = StrategyRunResponse(
            run_id="test_run",
            mission="test mission",
            candidates=[candidate],
            created_at=datetime.utcnow(),
        )
        
        result = service.save_strategy_run(response)
        
        self.assertTrue(result)
        # Verify execution data was saved
        calls = [call[0][0] for call in mock_client.table.call_args_list]
        self.assertIn("execution_results", calls)

    @patch('app.trading.persistence.get_supabase_client')
    def test_list_strategy_runs(self, mock_get_client):
        """Test listing strategy runs."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_runs = [
            {
                "run_id": "run1",
                "mission": "test mission 1",
                "created_at": "2024-01-01T00:00:00",
            },
            {
                "run_id": "run2",
                "mission": "test mission 2",
                "created_at": "2024-01-02T00:00:00",
            },
        ]
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.order.return_value.limit.return_value.offset.return_value.execute.return_value.data = mock_runs
        
        service = PersistenceService()
        
        runs = service.list_strategy_runs(limit=10, offset=0)
        
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0]["run_id"], "run1")

    @patch('app.trading.persistence.get_supabase_client')
    def test_get_strategy_run(self, mock_get_client):
        """Test getting a specific strategy run."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_run = {
            "run_id": "test_run",
            "mission": "test mission",
            "created_at": "2024-01-01T00:00:00",
        }
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.eq.return_value.execute.return_value.data = [mock_run]
        
        service = PersistenceService()
        
        run = service.get_strategy_run("test_run")
        
        self.assertIsNotNone(run)
        self.assertEqual(run["run_id"], "test_run")

    @patch('app.trading.persistence.get_supabase_client')
    def test_get_strategy_run_not_found(self, mock_get_client):
        """Test getting a non-existent strategy run."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.eq.return_value.execute.return_value.data = []
        
        service = PersistenceService()
        
        run = service.get_strategy_run("nonexistent")
        
        self.assertIsNone(run)


if __name__ == "__main__":
    unittest.main()

