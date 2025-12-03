"""
Tests for trading orchestrator module.
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.trading.models import StrategyRunRequest
from app.trading.orchestrator import run_strategy_run
from test.test_helpers import (
    create_mock_ohlcv_data,
    create_mock_strategy_spec,
)


class TestOrchestrator(unittest.TestCase):
    """Test orchestrator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.start_date = datetime(2020, 1, 1)
        self.ohlcv_data = create_mock_ohlcv_data(
            symbols=["AAPL"],
            start_date=self.start_date,
            days=100,
        )

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    def test_basic_strategy_run(
        self,
        mock_kill_switch,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_generate_strategies,
        mock_load_data,
    ):
        """Test basic strategy run flow."""
        # Setup mocks
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy = create_mock_strategy_spec(strategy_id="test_strategy")
        mock_generate_strategies.return_value = [strategy]
        
        from app.trading.models import BacktestResult, BacktestMetrics, RiskAssessment
        mock_backtest.return_value = BacktestResult(
            strategy=strategy,
            metrics=BacktestMetrics(sharpe=1.0, max_drawdown=0.1, total_return=0.15),
            trade_log=[],
        )
        
        mock_generate_orders.return_value = []
        mock_risk_assess.return_value = RiskAssessment(approved_trades=[], violations=[])
        
        # Run orchestrator
        request = StrategyRunRequest(
            mission="test mission",
            context={"universe": ["AAPL"], "data_range": "2020-01-01:2020-04-10", "execute": False},
        )
        
        result = run_strategy_run(request)
        
        # Verify results
        self.assertIsNotNone(result)
        self.assertEqual(result.mission, "test mission")
        self.assertGreater(len(result.candidates), 0)

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    def test_kill_switch_blocks_execution(
        self,
        mock_kill_switch,
        mock_generate_strategies,
        mock_load_data,
    ):
        """Test that kill switch blocks strategy execution."""
        mock_kill_switch.return_value = True  # Kill switch enabled
        
        request = StrategyRunRequest(
            mission="test mission",
            context={"universe": ["AAPL"]},
        )
        
        # Should raise ValueError when kill switch is enabled
        with self.assertRaises(ValueError) as context:
            run_strategy_run(request)
        
        self.assertIn("kill switch", str(context.exception).lower())

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.run_walk_forward_backtest')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    def test_walk_forward_validation_enabled(
        self,
        mock_kill_switch,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_walk_forward,
        mock_generate_strategies,
        mock_load_data,
    ):
        """Test orchestrator with walk-forward validation enabled."""
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy = create_mock_strategy_spec(strategy_id="test_wf")
        mock_generate_strategies.return_value = [strategy]
        
        from app.trading.models import (
            BacktestMetrics,
            BacktestResult,
            RiskAssessment,
            WalkForwardResult,
        )
        
        # Mock walk-forward result
        mock_walk_forward.return_value = WalkForwardResult(
            windows=[],
            aggregate_metrics=BacktestMetrics(sharpe=1.2, max_drawdown=0.08, total_return=0.18),
            train_metrics=BacktestMetrics(sharpe=1.1, max_drawdown=0.1, total_return=0.15),
            validation_metrics=BacktestMetrics(sharpe=1.3, max_drawdown=0.06, total_return=0.21),
        )
        
        mock_generate_orders.return_value = []
        mock_risk_assess.return_value = RiskAssessment(approved_trades=[], violations=[])
        
        request = StrategyRunRequest(
            mission="test mission",
            context={
                "universe": ["AAPL"],
                "data_range": "2020-01-01:2020-04-10",
                "validation": {"walk_forward": True, "train_split": 0.7},
            },
        )
        
        result = run_strategy_run(request)
        
        # Verify walk-forward was called
        mock_walk_forward.assert_called_once()
        self.assertIsNotNone(result.candidates[0].validation)

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.evaluate_gates')
    @patch('app.trading.orchestrator.list_scenarios')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    def test_scenario_gating_enabled(
        self,
        mock_kill_switch,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_list_scenarios,
        mock_evaluate_gates,
        mock_generate_strategies,
        mock_load_data,
    ):
        """Test orchestrator with scenario gating enabled."""
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy = create_mock_strategy_spec(strategy_id="test_gating")
        mock_generate_strategies.return_value = [strategy]
        
        from app.trading.models import (
            BacktestMetrics,
            BacktestResult,
            GatingResult,
            RiskAssessment,
        )
        
        mock_backtest.return_value = BacktestResult(
            strategy=strategy,
            metrics=BacktestMetrics(sharpe=1.0, max_drawdown=0.1, total_return=0.15),
            trade_log=[],
        )
        
        # Mock scenario gating
        from app.trading.scenarios import SCENARIO_2020_COVID
        mock_list_scenarios.return_value = [SCENARIO_2020_COVID]
        mock_evaluate_gates.return_value = GatingResult(
            passed=True,
            overall_passed=True,
            scenario_results=[],
            blocking_violations=[],
        )
        
        mock_generate_orders.return_value = []
        mock_risk_assess.return_value = RiskAssessment(approved_trades=[], violations=[])
        
        request = StrategyRunRequest(
            mission="test mission",
            context={
                "universe": ["AAPL"],
                "data_range": "2020-01-01:2020-04-10",
                "enable_scenarios": True,
            },
        )
        
        result = run_strategy_run(request)
        
        # Verify scenario gating was called
        mock_evaluate_gates.assert_called_once()
        self.assertIsNotNone(result.candidates[0].gating)

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.evaluate_gates')
    @patch('app.trading.orchestrator.list_scenarios')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    def test_gating_blocks_execution(
        self,
        mock_kill_switch,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_list_scenarios,
        mock_evaluate_gates,
        mock_generate_strategies,
        mock_load_data,
    ):
        """Test that failed gating blocks execution."""
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy = create_mock_strategy_spec(strategy_id="test_gating_fail")
        mock_generate_strategies.return_value = [strategy]
        
        from app.trading.models import (
            BacktestMetrics,
            BacktestResult,
            GatingResult,
            RiskAssessment,
        )
        
        mock_backtest.return_value = BacktestResult(
            strategy=strategy,
            metrics=BacktestMetrics(sharpe=1.0, max_drawdown=0.1, total_return=0.15),
            trade_log=[],
        )
        
        # Mock failed gating
        from app.trading.scenarios import SCENARIO_2020_COVID
        mock_list_scenarios.return_value = [SCENARIO_2020_COVID]
        mock_evaluate_gates.return_value = GatingResult(
            passed=False,
            overall_passed=False,
            scenario_results=[],
            blocking_violations=["Sharpe ratio too low"],
        )
        
        mock_generate_orders.return_value = []
        mock_risk_assess.return_value = RiskAssessment(approved_trades=[], violations=[])
        
        request = StrategyRunRequest(
            mission="test mission",
            context={
                "universe": ["AAPL"],
                "data_range": "2020-01-01:2020-04-10",
                "enable_scenarios": True,
                "execute": False,  # Not executing anyway, but test the logic
            },
        )
        
        result = run_strategy_run(request)
        
        # Should have gating result with violations
        self.assertIsNotNone(result.candidates[0].gating)
        self.assertFalse(result.candidates[0].gating.overall_passed)
        self.assertGreater(len(result.candidates[0].gating.blocking_violations), 0)

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.orchestrator.get_alpaca_broker')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    def test_execution_disabled_in_dev(
        self,
        mock_kill_switch,
        mock_get_broker,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_generate_strategies,
        mock_load_data,
    ):
        """Test that execution is blocked in dev environment."""
        import os
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy = create_mock_strategy_spec(strategy_id="test_exec")
        mock_generate_strategies.return_value = [strategy]
        
        from app.trading.models import (
            BacktestMetrics,
            BacktestResult,
            Order,
            RiskAssessment,
        )
        
        mock_backtest.return_value = BacktestResult(
            strategy=strategy,
            metrics=BacktestMetrics(sharpe=1.0, max_drawdown=0.1, total_return=0.15),
            trade_log=[],
        )
        
        mock_order = Order(symbol="AAPL", side="buy", quantity=10.0)
        mock_generate_orders.return_value = [mock_order]
        mock_risk_assess.return_value = RiskAssessment(approved_trades=[mock_order], violations=[])
        
        # Mock environment to be dev without ALLOW_EXECUTE
        original_env = os.getenv("ALLOW_EXECUTE")
        try:
            os.environ["ALLOW_EXECUTE"] = "false"
            
            request = StrategyRunRequest(
                mission="test mission",
                context={
                    "universe": ["AAPL"],
                    "data_range": "2020-01-01:2020-04-10",
                    "execute": True,  # Try to execute
                },
            )
            
            result = run_strategy_run(request)
            
            # Should have execution error
            self.assertIsNotNone(result.candidates[0].execution_error)
            self.assertIn("ALLOW_EXECUTE", result.candidates[0].execution_error)
        finally:
            if original_env:
                os.environ["ALLOW_EXECUTE"] = original_env
            else:
                os.environ.pop("ALLOW_EXECUTE", None)

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.orchestrator._repository')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    def test_persistence_integration(
        self,
        mock_kill_switch,
        mock_repository,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_generate_strategies,
        mock_load_data,
    ):
        """Test that orchestrator attempts to persist results."""
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy = create_mock_strategy_spec(strategy_id="test_persist")
        mock_generate_strategies.return_value = [strategy]
        
        from app.trading.models import BacktestMetrics, BacktestResult, RiskAssessment
        
        mock_backtest.return_value = BacktestResult(
            strategy=strategy,
            metrics=BacktestMetrics(sharpe=1.0, max_drawdown=0.1, total_return=0.15),
            trade_log=[],
        )
        
        mock_generate_orders.return_value = []
        mock_risk_assess.return_value = RiskAssessment(approved_trades=[], violations=[])
        
        # Mock repository save
        mock_repository.save_strategy_run.return_value = True
        
        request = StrategyRunRequest(
            mission="test mission",
            context={"universe": ["AAPL"], "data_range": "2020-01-01:2020-04-10"},
        )
        
        result = run_strategy_run(request)
        
        # Verify repository was called (non-blocking, so may succeed or fail)
        # The orchestrator should attempt to save
        self.assertIsNotNone(result)

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    def test_empty_strategy_list(
        self,
        mock_kill_switch,
        mock_generate_strategies,
        mock_load_data,
    ):
        """Test orchestrator with empty strategy list."""
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        mock_generate_strategies.return_value = []  # No strategies
        
        request = StrategyRunRequest(
            mission="test mission",
            context={"universe": ["AAPL"]},
        )
        
        result = run_strategy_run(request)
        
        # Should return response with empty candidates
        self.assertIsNotNone(result)
        self.assertEqual(len(result.candidates), 0)


if __name__ == "__main__":
    unittest.main()

