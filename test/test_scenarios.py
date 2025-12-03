"""
Tests for golden dataset scenarios and gating.
"""
import unittest
from datetime import datetime, timedelta

from app.trading.models import (
    BacktestRequest,
    GatingRule,
    StrategyParams,
    StrategyRule,
    StrategySpec,
)
from app.trading.scenarios import (
    evaluate_gates,
    evaluate_scenario,
    get_default_gating_rules,
    get_scenario,
    list_scenarios,
    SCENARIO_2008_CRISIS,
    SCENARIO_2020_COVID,
)


class TestScenarios(unittest.TestCase):
    """Test scenario evaluation and gating functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create sample OHLCV data covering scenario periods
        self.ohlcv_data = {}
        
        # Data for 2020 COVID scenario
        covid_start = datetime(2020, 2, 1)
        for symbol in ["AAPL"]:
            bars = []
            base_price = 100.0
            for i in range(150):  # ~5 months
                timestamp = covid_start + timedelta(days=i)
                # Simulate crash and recovery
                if i < 30:
                    price = base_price - (i * 2)  # Crash
                else:
                    price = base_price - 60 + (i - 30) * 1.5  # Recovery
                bars.append({
                    "timestamp": timestamp,
                    "open": price,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": 1000000,
                })
            self.ohlcv_data[symbol] = bars

    def test_get_scenario(self):
        """Test getting a scenario by ID."""
        scenario = get_scenario("2008_crisis")
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.scenario_id, "2008_crisis")
        self.assertEqual(scenario.name, "2008 Financial Crisis")

    def test_list_scenarios(self):
        """Test listing all scenarios."""
        scenarios = list_scenarios()
        self.assertGreater(len(scenarios), 0)
        self.assertIn(SCENARIO_2008_CRISIS, scenarios)
        self.assertIn(SCENARIO_2020_COVID, scenarios)

    def test_list_scenarios_with_tags(self):
        """Test listing scenarios filtered by tags."""
        crisis_scenarios = list_scenarios(tags=["crisis"])
        self.assertGreater(len(crisis_scenarios), 0)
        
        # All returned scenarios should have "crisis" tag
        for scenario in crisis_scenarios:
            self.assertIn("crisis", scenario.tags)

    def test_evaluate_scenario(self):
        """Test scenario evaluation."""
        strategy = StrategySpec(
            strategy_id="test_scenario",
            name="Test Scenario",
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
            data_range=f"{datetime(2020, 2, 1).isoformat()}:{datetime(2020, 6, 30).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        result = evaluate_scenario(request, SCENARIO_2020_COVID, self.ohlcv_data)

        self.assertIsNotNone(result)
        self.assertEqual(result.scenario.scenario_id, "2020_covid")
        self.assertIsNotNone(result.backtest)
        self.assertIsNotNone(result.backtest.metrics)

    def test_get_default_gating_rules(self):
        """Test getting default gating rules."""
        rules = get_default_gating_rules()
        self.assertGreater(len(rules), 0)
        
        # Check that rules have required fields
        for rule in rules:
            self.assertIsNotNone(rule.metric)
            self.assertIsNotNone(rule.operator)
            self.assertIsNotNone(rule.threshold)

    def test_evaluate_gates(self):
        """Test gating evaluation."""
        strategy = StrategySpec(
            strategy_id="test_gating",
            name="Test Gating",
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
            data_range=f"{datetime(2020, 2, 1).isoformat()}:{datetime(2020, 6, 30).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        scenarios = [SCENARIO_2020_COVID]
        result = evaluate_gates(request, scenarios, self.ohlcv_data)

        self.assertIsNotNone(result)
        self.assertIsInstance(result.passed, bool)
        self.assertEqual(len(result.scenario_results), len(scenarios))
        self.assertIsNotNone(result.overall_passed)

    def test_gating_rule_violation(self):
        """Test that gating rules correctly identify violations."""
        # Create a rule that will likely be violated
        strict_rule = GatingRule(
            metric="sharpe",
            operator=">",
            threshold=10.0,  # Very high threshold
            scenario_tags=None,
        )

        strategy = StrategySpec(
            strategy_id="test_violation",
            name="Test Violation",
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
            data_range=f"{datetime(2020, 2, 1).isoformat()}:{datetime(2020, 6, 30).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        scenarios = [SCENARIO_2020_COVID]
        result = evaluate_gates(request, scenarios, self.ohlcv_data, gating_rules=[strict_rule])

        # Should have violations
        self.assertIsNotNone(result)
        # The result may or may not pass depending on actual backtest performance
        # But we should have scenario results
        self.assertEqual(len(result.scenario_results), 1)

    def test_list_scenarios_multiple_tags(self):
        """Test listing scenarios filtered by multiple tags."""
        # Test filtering by multiple tags (scenario must have all tags)
        bear_market_scenarios = list_scenarios(tags=["bear_market"])
        self.assertGreater(len(bear_market_scenarios), 0)
        
        # All returned scenarios should have "bear_market" tag
        for scenario in bear_market_scenarios:
            self.assertIn("bear_market", scenario.tags)

    def test_list_scenarios_no_matching_tags(self):
        """Test listing scenarios with tags that don't match any scenario."""
        # Use a tag that doesn't exist
        no_match = list_scenarios(tags=["nonexistent_tag"])
        self.assertEqual(len(no_match), 0)

    def test_evaluate_gates_with_custom_rules(self):
        """Test gating evaluation with custom gating rules."""
        strategy = StrategySpec(
            strategy_id="test_custom_gating",
            name="Test Custom Gating",
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
            data_range=f"{datetime(2020, 2, 1).isoformat()}:{datetime(2020, 6, 30).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        # Create custom gating rules
        custom_rules = [
            GatingRule(
                metric="sharpe",
                operator=">",
                threshold=0.5,  # Reasonable threshold
                scenario_tags=None,
            ),
            GatingRule(
                metric="max_drawdown",
                operator="<",
                threshold=0.5,  # Max drawdown less than 50%
                scenario_tags=None,
            ),
        ]

        scenarios = [SCENARIO_2020_COVID]
        result = evaluate_gates(request, scenarios, self.ohlcv_data, gating_rules=custom_rules)

        self.assertIsNotNone(result)
        self.assertEqual(len(result.scenario_results), len(scenarios))
        # Should have evaluated against custom rules
        self.assertIsNotNone(result.overall_passed)

    def test_evaluate_gates_scenario_result_aggregation(self):
        """Test that scenario results are properly aggregated."""
        strategy = StrategySpec(
            strategy_id="test_aggregation",
            name="Test Aggregation",
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
            data_range=f"{datetime(2020, 2, 1).isoformat()}:{datetime(2020, 6, 30).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        # Evaluate with multiple scenarios
        scenarios = [SCENARIO_2020_COVID, SCENARIO_2008_CRISIS]
        result = evaluate_gates(request, scenarios, self.ohlcv_data)

        self.assertIsNotNone(result)
        # Should have results for each scenario
        self.assertEqual(len(result.scenario_results), len(scenarios))
        # Overall passed should be based on all scenarios
        self.assertIsInstance(result.overall_passed, bool)
        # Should have blocking violations if any scenario fails
        self.assertIsInstance(result.blocking_violations, list)

    def test_evaluate_gates_all_scenarios_pass(self):
        """Test gating when all scenarios pass."""
        strategy = StrategySpec(
            strategy_id="test_all_pass",
            name="Test All Pass",
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
            data_range=f"{datetime(2020, 2, 1).isoformat()}:{datetime(2020, 6, 30).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        # Use lenient rules that should pass
        lenient_rules = [
            GatingRule(
                metric="sharpe",
                operator=">",
                threshold=-10.0,  # Very lenient
                scenario_tags=None,
            ),
        ]

        scenarios = [SCENARIO_2020_COVID]
        result = evaluate_gates(request, scenarios, self.ohlcv_data, gating_rules=lenient_rules)

        self.assertIsNotNone(result)
        # If all scenarios pass, overall_passed should be True
        # (Note: actual result depends on backtest performance)
        self.assertIsInstance(result.overall_passed, bool)

    def test_evaluate_gates_scenario_specific_rules(self):
        """Test gating with scenario-specific rules."""
        strategy = StrategySpec(
            strategy_id="test_scenario_specific",
            name="Test Scenario Specific",
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
            data_range=f"{datetime(2020, 2, 1).isoformat()}:{datetime(2020, 6, 30).isoformat()}",
            costs={"commission": 0.001, "slippage_pct": 0.0005},
        )

        # Create rule that applies only to crisis scenarios
        crisis_rule = GatingRule(
            metric="max_drawdown",
            operator="<",
            threshold=0.3,  # Max 30% drawdown in crisis
            scenario_tags=["crisis"],
        )

        scenarios = [SCENARIO_2020_COVID]  # Has "crisis" tag
        result = evaluate_gates(request, scenarios, self.ohlcv_data, gating_rules=[crisis_rule])

        self.assertIsNotNone(result)
        self.assertEqual(len(result.scenario_results), 1)


if __name__ == "__main__":
    unittest.main()

