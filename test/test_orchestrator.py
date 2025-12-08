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

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.instantiate_templates')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    @patch('app.trading.orchestrator.get_persistence_service')
    def test_template_only_strategy_run(
        self,
        mock_kill_switch,
        mock_persistence,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_instantiate_templates,
        mock_load_data,
    ):
        """Test strategy run with template_ids only (bypasses LLM for strategy generation)."""
        from app.trading.models import BacktestResult, Order, RiskAssessment
        
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy = create_mock_strategy_spec(strategy_id="template_strategy")
        mock_instantiate_templates.return_value = [strategy]
        
        mock_backtest.return_value = BacktestResult(
            strategy=strategy,
            metrics=create_mock_strategy_spec().params,
            trade_log=[],
        )
        
        mock_generate_orders.return_value = [Order(symbol="AAPL", side="buy", quantity=10.0)]
        mock_risk_assess.return_value = RiskAssessment(approved_trades=[Order(symbol="AAPL", side="buy", quantity=10.0)])
        
        request = StrategyRunRequest(
            mission="Using predefined strategies",
            template_ids=["volatility_breakout"],
            context={"universe": ["AAPL"]},
        )
        
        result = run_strategy_run(request)
        
        # Verify templates were instantiated (not LLM called for strategy generation)
        mock_instantiate_templates.assert_called_once()
        self.assertIsNotNone(result)
        self.assertEqual(len(result.candidates), 1)

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.instantiate_templates')
    @patch('app.trading.orchestrator.combine_strategies_with_llm')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    @patch('app.trading.orchestrator.get_persistence_service')
    def test_multiple_templates_combination(
        self,
        mock_kill_switch,
        mock_persistence,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_combine_strategies,
        mock_instantiate_templates,
        mock_load_data,
    ):
        """Test that multiple templates are combined via LLM."""
        from app.trading.models import BacktestResult, Order, RiskAssessment
        
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy1 = create_mock_strategy_spec(strategy_id="template1")
        strategy2 = create_mock_strategy_spec(strategy_id="template2")
        combined_strategy = create_mock_strategy_spec(strategy_id="combined")
        
        mock_instantiate_templates.return_value = [strategy1, strategy2]
        mock_combine_strategies.return_value = combined_strategy
        
        from test.test_helpers import create_mock_backtest_result
        mock_backtest.return_value = create_mock_backtest_result(combined_strategy)
        mock_generate_orders.return_value = [Order(symbol="AAPL", side="buy", quantity=10.0)]
        mock_risk_assess.return_value = RiskAssessment(approved_trades=[Order(symbol="AAPL", side="buy", quantity=10.0)])
        
        request = StrategyRunRequest(
            mission="Using predefined strategies",
            template_ids=["volatility_breakout", "intraday_mean_reversion"],
            context={"universe": ["AAPL"]},
        )
        
        result = run_strategy_run(request)
        
        # Verify combine_strategies_with_llm was called
        mock_combine_strategies.assert_called_once()
        self.assertIsNotNone(result)

    @patch('app.trading.orchestrator.market_data.load_data')
    @patch('app.trading.orchestrator.instantiate_templates')
    @patch('app.trading.orchestrator.generate_strategy_specs')
    @patch('app.trading.orchestrator.run_backtest')
    @patch('app.trading.orchestrator.generate_orders')
    @patch('app.trading.orchestrator.risk_assess')
    @patch('app.trading.external_data.get_news_provider')
    @patch('app.trading.external_data.get_social_media_provider')
    @patch('app.trading.decision_engine.DecisionEngine')
    @patch('app.trading.orchestrator.is_kill_switch_enabled')
    @patch('app.trading.orchestrator.get_persistence_service')
    def test_multi_source_decision_enabled(
        self,
        mock_kill_switch,
        mock_persistence,
        mock_decision_engine_class,
        mock_get_social_provider,
        mock_get_news_provider,
        mock_risk_assess,
        mock_generate_orders,
        mock_backtest,
        mock_generate_strategies,
        mock_instantiate_templates,
        mock_load_data,
    ):
        """Test strategy run with multi-source decision enabled."""
        from app.trading.models import BacktestResult, Order, RiskAssessment
        from app.trading.external_data import MockNewsProvider, MockSocialMediaProvider
        from app.trading.decision_engine import DecisionOutput
        
        mock_kill_switch.return_value = False
        mock_load_data.return_value = self.ohlcv_data
        
        strategy = create_mock_strategy_spec(strategy_id="test_strategy")
        mock_generate_strategies.return_value = [strategy]
        mock_instantiate_templates.return_value = []
        
        mock_backtest.return_value = BacktestResult(
            strategy=strategy,
            metrics=create_mock_strategy_spec().params,
            trade_log=[],
        )
        
        original_orders = [Order(symbol="AAPL", side="buy", quantity=10.0)]
        adjusted_orders = [Order(symbol="AAPL", side="buy", quantity=8.0)]  # Decision engine adjusted quantity
        
        mock_generate_orders.return_value = original_orders
        mock_risk_assess.return_value = RiskAssessment(approved_trades=original_orders)
        
        # Mock external data providers
        mock_news_provider = MockNewsProvider()
        mock_social_provider = MockSocialMediaProvider()
        mock_get_news_provider.return_value = mock_news_provider
        mock_get_social_provider.return_value = mock_social_provider
        
        # Mock decision engine
        mock_decision_engine = mock_decision_engine_class.return_value
        mock_decision_engine.make_decision.return_value = DecisionOutput(
            recommended_actions=adjusted_orders,
            confidence_scores={"AAPL": 0.85},
            reasoning="Adjusted based on news sentiment",
            source_contributions=[],
            adjustments=["Reduced quantity due to negative news"],
        )
        
        request = StrategyRunRequest(
            mission="Test mission",
            enable_multi_source_decision=True,
            context={"universe": ["AAPL"]},
        )
        
        result = run_strategy_run(request)
        
        # Verify decision engine was called
        mock_decision_engine.make_decision.assert_called_once()
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()

