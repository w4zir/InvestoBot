"""
Tests for strategy planner module.
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from app.agents.strategy_planner import (
    _calculate_strategy_similarity,
    _ensure_strategy_diversity,
    _extract_json_from_text,
    _fix_strategy_constraints,
    _validate_strategy_constraints,
    generate_strategy_specs,
)
from app.trading.models import StrategyParams, StrategyRule, StrategySpec
from test.test_helpers import (
    create_mock_llm_response,
    create_mock_llm_response_with_text,
    create_mock_strategy_spec,
)


class TestStrategyPlanner(unittest.TestCase):
    """Test strategy planner functionality."""

    def test_extract_json_from_plain_text(self):
        """Test JSON extraction from plain text."""
        json_data = {"strategies": [{"strategy_id": "test1"}]}
        text = json.dumps(json_data)
        
        extracted = _extract_json_from_text(text)
        parsed = json.loads(extracted)
        
        self.assertEqual(parsed["strategies"][0]["strategy_id"], "test1")

    def test_extract_json_from_markdown(self):
        """Test JSON extraction from markdown code blocks."""
        json_data = {"strategies": [{"strategy_id": "test1"}]}
        json_str = json.dumps(json_data)
        text = f"```json\n{json_str}\n```"
        
        extracted = _extract_json_from_text(text)
        parsed = json.loads(extracted)
        
        self.assertEqual(parsed["strategies"][0]["strategy_id"], "test1")

    def test_extract_json_from_markdown_no_lang(self):
        """Test JSON extraction from markdown code blocks without language."""
        json_data = {"strategies": [{"strategy_id": "test1"}]}
        json_str = json.dumps(json_data)
        text = f"```\n{json_str}\n```"
        
        extracted = _extract_json_from_text(text)
        parsed = json.loads(extracted)
        
        self.assertEqual(parsed["strategies"][0]["strategy_id"], "test1")

    def test_extract_json_with_text_before_after(self):
        """Test JSON extraction when text appears before and after JSON."""
        json_data = {"strategies": [{"strategy_id": "test1"}]}
        json_str = json.dumps(json_data)
        text = f"Here is the response:\n{json_str}\nThese are the strategies."
        
        extracted = _extract_json_from_text(text)
        parsed = json.loads(extracted)
        
        self.assertEqual(parsed["strategies"][0]["strategy_id"], "test1")

    def test_extract_json_empty_text(self):
        """Test JSON extraction from empty text."""
        extracted = _extract_json_from_text("")
        self.assertEqual(extracted, "")

    def test_validate_strategy_constraints_valid(self):
        """Test validation of valid strategy."""
        strategy = create_mock_strategy_spec(
            strategy_id="valid_strategy",
            universe=["AAPL"],
            fraction=0.02,
        )
        
        errors = _validate_strategy_constraints(strategy)
        self.assertEqual(len(errors), 0)

    def test_validate_strategy_constraints_fraction_too_small(self):
        """Test validation catches fraction that's too small."""
        strategy = create_mock_strategy_spec(
            strategy_id="small_fraction",
            universe=["AAPL"],
            fraction=0.005,  # Below minimum 0.01
        )
        
        errors = _validate_strategy_constraints(strategy)
        self.assertGreater(len(errors), 0)
        self.assertIn("fraction", errors[0].lower())

    def test_validate_strategy_constraints_fraction_too_large(self):
        """Test validation catches fraction that's too large."""
        strategy = create_mock_strategy_spec(
            strategy_id="large_fraction",
            universe=["AAPL"],
            fraction=0.10,  # Above maximum 0.05
        )
        
        errors = _validate_strategy_constraints(strategy)
        self.assertGreater(len(errors), 0)
        self.assertIn("fraction", errors[0].lower())

    def test_validate_strategy_constraints_empty_universe(self):
        """Test validation catches empty universe."""
        strategy = create_mock_strategy_spec(
            strategy_id="empty_universe",
            universe=[],  # Empty universe
            fraction=0.02,
        )
        
        errors = _validate_strategy_constraints(strategy)
        self.assertGreater(len(errors), 0)
        self.assertIn("universe", errors[0].lower())

    def test_validate_strategy_constraints_empty_rules(self):
        """Test validation catches empty rules."""
        strategy = StrategySpec(
            strategy_id="empty_rules",
            name="Empty Rules Strategy",
            universe=["AAPL"],
            rules=[],  # Empty rules
            params=StrategyParams(
                position_sizing="fixed_fraction",
                fraction=0.02,
            ),
        )
        
        errors = _validate_strategy_constraints(strategy)
        self.assertGreater(len(errors), 0)
        self.assertIn("rules", errors[0].lower())

    def test_fix_strategy_constraints_fraction_too_small(self):
        """Test constraint fixing adjusts fraction that's too small."""
        strategy = create_mock_strategy_spec(
            strategy_id="fix_small_fraction",
            universe=["AAPL"],
            fraction=0.005,  # Too small
        )
        
        fixed = _fix_strategy_constraints(strategy)
        self.assertGreaterEqual(fixed.params.fraction, 0.01)

    def test_fix_strategy_constraints_fraction_too_large(self):
        """Test constraint fixing adjusts fraction that's too large."""
        strategy = create_mock_strategy_spec(
            strategy_id="fix_large_fraction",
            universe=["AAPL"],
            fraction=0.10,  # Too large
        )
        
        fixed = _fix_strategy_constraints(strategy)
        self.assertLessEqual(fixed.params.fraction, 0.05)

    def test_fix_strategy_constraints_blacklisted_symbols(self):
        """Test constraint fixing removes blacklisted symbols."""
        from app.core.config import get_settings
        
        settings = get_settings()
        blacklisted = settings.risk.blacklist_symbols
        
        if blacklisted:
            # Use first blacklisted symbol
            blacklisted_symbol = blacklisted[0]
            strategy = create_mock_strategy_spec(
                strategy_id="fix_blacklist",
                universe=[blacklisted_symbol, "AAPL"],
                fraction=0.02,
            )
            
            fixed = _fix_strategy_constraints(strategy)
            self.assertNotIn(blacklisted_symbol, fixed.universe)

    def test_calculate_strategy_similarity_identical(self):
        """Test similarity calculation for identical strategies."""
        strategy1 = create_mock_strategy_spec(
            strategy_id="strategy1",
            universe=["AAPL"],
            fraction=0.02,
        )
        strategy2 = create_mock_strategy_spec(
            strategy_id="strategy2",
            universe=["AAPL"],
            fraction=0.02,
        )
        
        similarity = _calculate_strategy_similarity(strategy1, strategy2)
        # Should have high similarity (same universe, same rules)
        self.assertGreater(similarity, 0.5)

    def test_calculate_strategy_similarity_different(self):
        """Test similarity calculation for different strategies."""
        strategy1 = create_mock_strategy_spec(
            strategy_id="strategy1",
            universe=["AAPL"],
            fraction=0.02,
        )
        strategy2 = create_mock_strategy_spec(
            strategy_id="strategy2",
            universe=["MSFT"],
            fraction=0.03,
        )
        
        similarity = _calculate_strategy_similarity(strategy1, strategy2)
        # Should have lower similarity
        self.assertLess(similarity, 1.0)

    def test_ensure_strategy_diversity_no_duplicates(self):
        """Test diversity check with no duplicate IDs."""
        strategies = [
            create_mock_strategy_spec(strategy_id="strategy1", universe=["AAPL"]),
            create_mock_strategy_spec(strategy_id="strategy2", universe=["MSFT"]),
        ]
        
        # Should not raise exception
        _ensure_strategy_diversity(strategies)

    def test_ensure_strategy_diversity_with_duplicates(self):
        """Test diversity check logs warning for duplicate IDs."""
        strategies = [
            create_mock_strategy_spec(strategy_id="duplicate", universe=["AAPL"]),
            create_mock_strategy_spec(strategy_id="duplicate", universe=["MSFT"]),
        ]
        
        # Should log warning but not raise exception
        _ensure_strategy_diversity(strategies)

    @patch('app.agents.strategy_planner.get_google_agent_client')
    def test_generate_strategy_specs_success(self, mock_get_client):
        """Test successful strategy generation from LLM response."""
        # Mock the Google client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Create mock LLM response
        strategies_data = [
            {
                "strategy_id": "test_strategy",
                "name": "Test Strategy",
                "universe": ["AAPL"],
                "rules": [
                    {
                        "type": "entry",
                        "indicator": "sma",
                        "params": {"window": 10, "threshold": 0, "direction": "above"},
                    },
                ],
                "params": {
                    "position_sizing": "fixed_fraction",
                    "fraction": 0.02,
                    "timeframe": "1d",
                },
            }
        ]
        
        mock_response = create_mock_llm_response(strategies_data)
        mock_client.plan_strategy.return_value = {"raw_text": mock_response}
        
        # Generate strategies
        result = generate_strategy_specs(mission="test mission", context={})
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].strategy_id, "test_strategy")

    @patch('app.agents.strategy_planner.get_google_agent_client')
    def test_generate_strategy_specs_empty_response(self, mock_get_client):
        """Test strategy generation with empty LLM response."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.plan_strategy.return_value = {"raw_text": ""}
        
        # Should raise ValueError
        with self.assertRaises(ValueError):
            generate_strategy_specs(mission="test mission", context={})

    @patch('app.agents.strategy_planner.get_google_agent_client')
    def test_generate_strategy_specs_invalid_json(self, mock_get_client):
        """Test strategy generation with invalid JSON response."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.plan_strategy.return_value = {"raw_text": "This is not JSON"}
        
        # Should raise ValueError
        with self.assertRaises(ValueError):
            generate_strategy_specs(mission="test mission", context={})

    @patch('app.agents.strategy_planner.get_google_agent_client')
    def test_generate_strategy_specs_markdown_wrapped(self, mock_get_client):
        """Test strategy generation with markdown-wrapped JSON."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        strategies_data = [
            {
                "strategy_id": "test_strategy",
                "universe": ["AAPL"],
                "rules": [
                    {
                        "type": "entry",
                        "indicator": "sma",
                        "params": {"window": 10},
                    },
                ],
                "params": {
                    "position_sizing": "fixed_fraction",
                    "fraction": 0.02,
                },
            }
        ]
        
        mock_response = create_mock_llm_response(strategies_data, wrapped_in_markdown=True)
        mock_client.plan_strategy.return_value = {"raw_text": mock_response}
        
        result = generate_strategy_specs(mission="test mission", context={})
        self.assertEqual(len(result), 1)

    @patch('app.agents.strategy_planner.get_google_agent_client')
    def test_generate_strategy_specs_with_text(self, mock_get_client):
        """Test strategy generation with text before/after JSON."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        strategies_data = [
            {
                "strategy_id": "test_strategy",
                "universe": ["AAPL"],
                "rules": [
                    {
                        "type": "entry",
                        "indicator": "sma",
                        "params": {"window": 10},
                    },
                ],
                "params": {
                    "position_sizing": "fixed_fraction",
                    "fraction": 0.02,
                },
            }
        ]
        
        mock_response = create_mock_llm_response_with_text(strategies_data)
        mock_client.plan_strategy.return_value = {"raw_text": mock_response}
        
        result = generate_strategy_specs(mission="test mission", context={})
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()

