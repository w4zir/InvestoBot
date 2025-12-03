"""
Tests for repository module.
"""
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.core.repository import RunRepository
from app.trading.models import (
    BacktestMetrics,
    BacktestResult,
    CandidateResult,
    Fill,
    RiskAssessment,
    StrategyRunResponse,
    Trade,
)
from test.test_helpers import (
    create_mock_backtest_result,
    create_mock_strategy_spec,
)


class TestRunRepository(unittest.TestCase):
    """Test repository functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.strategy = create_mock_strategy_spec(strategy_id="test_repo")
        self.backtest_result = create_mock_backtest_result(
            strategy=self.strategy,
            sharpe=1.0,
            max_drawdown=0.1,
            total_return=0.15,
        )

    @patch('app.core.repository.get_supabase_client')
    def test_initialization_with_client(self, mock_get_client):
        """Test repository initialization with Supabase client."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        repository = RunRepository()
        
        self.assertIsNotNone(repository.client)
        self.assertEqual(repository.client, mock_client)

    @patch('app.core.repository.get_supabase_client')
    def test_initialization_without_client(self, mock_get_client):
        """Test repository initialization without Supabase client."""
        mock_get_client.return_value = None
        
        repository = RunRepository()
        
        self.assertIsNone(repository.client)

    @patch('app.core.repository.get_supabase_client')
    def test_save_run_success(self, mock_get_client):
        """Test successful run save."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = None
        
        repository = RunRepository()
        
        response = StrategyRunResponse(
            run_id="test_run",
            mission="test mission",
            candidates=[],
            created_at=datetime.utcnow(),
        )
        
        result = repository.save_run(response, context={"universe": ["AAPL"]})
        
        self.assertTrue(result)
        mock_table.upsert.assert_called_once()

    @patch('app.core.repository.get_supabase_client')
    def test_save_backtest_result(self, mock_get_client):
        """Test saving backtest result."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value.data = [{"id": str(uuid4())}]
        
        repository = RunRepository()
        
        backtest_id = repository.save_backtest_result(
            run_id="test_run",
            strategy_id="test_strategy",
            backtest=self.backtest_result,
            data_range="2020-01-01:2020-04-10",
        )
        
        self.assertIsNotNone(backtest_id)
        mock_table.insert.assert_called_once()

    @patch('app.core.repository.get_supabase_client')
    def test_save_trades(self, mock_get_client):
        """Test saving trades."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value = None
        
        repository = RunRepository()
        
        trades = [
            Trade(
                timestamp=datetime.utcnow(),
                symbol="AAPL",
                side="buy",
                quantity=10.0,
                price=150.0,
            )
        ]
        
        count = repository.save_trades("test_run", "test_strategy", trades)
        
        self.assertEqual(count, 1)
        mock_table.insert.assert_called_once()

    @patch('app.core.repository.get_supabase_client')
    def test_save_risk_violations(self, mock_get_client):
        """Test saving risk violations."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value = None
        
        repository = RunRepository()
        
        risk_assessment = RiskAssessment(
            approved_trades=[],
            violations=["Symbol BLACKLISTED is blacklisted"],
        )
        
        count = repository.save_risk_violations("test_run", "test_strategy", risk_assessment)
        
        self.assertEqual(count, 1)
        mock_table.insert.assert_called_once()

    @patch('app.core.repository.get_supabase_client')
    def test_save_fills(self, mock_get_client):
        """Test saving execution fills."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value = None
        
        repository = RunRepository()
        
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
        
        count = repository.save_fills("test_run", "test_strategy", fills)
        
        self.assertEqual(count, 1)
        mock_table.insert.assert_called_once()

    @patch('app.core.repository.get_supabase_client')
    def test_save_candidate_result(self, mock_get_client):
        """Test saving complete candidate result."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value.data = [{"id": str(uuid4())}]
        mock_table.upsert.return_value.execute.return_value = None
        
        repository = RunRepository()
        
        candidate = CandidateResult(
            strategy=self.strategy,
            backtest=self.backtest_result,
            risk=RiskAssessment(approved_trades=[], violations=[]),
            execution_fills=[],
            execution_error=None,
        )
        
        result = repository.save_candidate_result(
            run_id="test_run",
            candidate=candidate,
            data_range="2020-01-01:2020-04-10",
        )
        
        self.assertTrue(result)
        # Verify multiple table operations were called
        self.assertGreater(mock_client.table.call_count, 1)

    @patch('app.core.repository.get_supabase_client')
    def test_save_strategy_run_complete(self, mock_get_client):
        """Test saving complete strategy run with all candidates."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value.data = [{"id": str(uuid4())}]
        mock_table.upsert.return_value.execute.return_value = None
        
        repository = RunRepository()
        
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
        
        result = repository.save_strategy_run(response, context={"universe": ["AAPL"]})
        
        self.assertTrue(result)

    @patch('app.core.repository.get_supabase_client')
    def test_save_with_no_client(self, mock_get_client):
        """Test repository operations when client is unavailable."""
        mock_get_client.return_value = None
        
        repository = RunRepository()
        
        response = StrategyRunResponse(
            run_id="test_run",
            mission="test mission",
            candidates=[],
            created_at=datetime.utcnow(),
        )
        
        # Should return False but not raise exception
        result = repository.save_strategy_run(response)
        self.assertFalse(result)

    @patch('app.core.repository.get_supabase_client')
    def test_save_with_error(self, mock_get_client):
        """Test repository handles errors gracefully."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.side_effect = Exception("Database error")
        
        repository = RunRepository()
        
        response = StrategyRunResponse(
            run_id="test_run",
            mission="test mission",
            candidates=[],
            created_at=datetime.utcnow(),
        )
        
        # Should return False but not raise exception
        result = repository.save_strategy_run(response)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()

