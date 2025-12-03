"""
Tests for Google Agent Client module.
"""
import unittest
from unittest.mock import MagicMock, patch

from app.agents.google_client import GoogleAgentClient
from app.core.config import get_settings


class TestGoogleClient(unittest.TestCase):
    """Test Google Agent Client functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.settings = get_settings()
        # Store original API key
        self.original_api_key = self.settings.google.api_key

    def tearDown(self):
        """Clean up after tests."""
        # Restore original API key
        if hasattr(self, 'original_api_key'):
            self.settings.google.api_key = self.original_api_key

    @patch('app.agents.google_client.genai')
    def test_initialization_with_api_key(self, mock_genai):
        """Test client initialization with valid API key."""
        self.settings.google.api_key = "test_api_key"
        mock_genai.Client.return_value = MagicMock()
        
        client = GoogleAgentClient()
        
        self.assertIsNotNone(client._client)
        mock_genai.Client.assert_called_once_with(api_key="test_api_key")

    def test_initialization_without_api_key(self):
        """Test client initialization fails without API key."""
        self.settings.google.api_key = None
        
        with self.assertRaises(ValueError):
            GoogleAgentClient()

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_build_risk_constraints_section(self, mock_get_registry, mock_genai):
        """Test risk constraints section building."""
        self.settings.google.api_key = "test_key"
        mock_genai.Client.return_value = MagicMock()
        
        client = GoogleAgentClient()
        constraints = client._build_risk_constraints_section()
        
        self.assertIn("RISK CONSTRAINTS", constraints)
        self.assertIn("Position Sizing", constraints)
        self.assertIn("Trade Notional Limits", constraints)
        self.assertIn("Blacklisted Symbols", constraints)

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_build_template_section_with_templates(self, mock_get_registry, mock_genai):
        """Test template section building with templates."""
        self.settings.google.api_key = "test_key"
        mock_genai.Client.return_value = MagicMock()
        
        # Mock template registry
        mock_registry = MagicMock()
        mock_registry.get_template_examples.return_value = [
            {
                "template_id": "test_template",
                "template_name": "Test Template",
                "description": "A test template",
                "example_strategy": {
                    "strategy_id": "example_1",
                    "name": "Example",
                    "universe": ["AAPL"],
                    "rules": [],
                    "params": {},
                }
            }
        ]
        mock_get_registry.return_value = mock_registry
        
        client = GoogleAgentClient()
        template_section = client._build_template_section(mock_registry.get_template_examples())
        
        self.assertIn("STRATEGY TEMPLATES", template_section)
        self.assertIn("Test Template", template_section)

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_build_template_section_empty(self, mock_get_registry, mock_genai):
        """Test template section building with no templates."""
        self.settings.google.api_key = "test_key"
        mock_genai.Client.return_value = MagicMock()
        
        client = GoogleAgentClient()
        template_section = client._build_template_section([])
        
        self.assertEqual(template_section, "")

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_build_examples_section(self, mock_get_registry, mock_genai):
        """Test examples section building."""
        self.settings.google.api_key = "test_key"
        mock_genai.Client.return_value = MagicMock()
        
        examples = [
            {
                "template_id": "test_template",
                "template_name": "Test Template",
                "example_strategy": {
                    "strategy_id": "example_1",
                    "name": "Example",
                    "universe": ["AAPL"],
                    "rules": [],
                    "params": {},
                }
            }
        ]
        
        client = GoogleAgentClient()
        examples_section = client._build_examples_section(examples)
        
        self.assertIn("FEW-SHOT EXAMPLES", examples_section)
        self.assertIn("Test Template", examples_section)

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_build_enhanced_prompt(self, mock_get_registry, mock_genai):
        """Test enhanced prompt building."""
        self.settings.google.api_key = "test_key"
        mock_genai.Client.return_value = MagicMock()
        
        client = GoogleAgentClient()
        risk_constraints = "=== RISK CONSTRAINTS ===\nTest constraints"
        template_section = "=== TEMPLATES ===\nTest templates"
        examples_section = "=== EXAMPLES ===\nTest examples"
        
        prompt = client._build_enhanced_prompt(risk_constraints, template_section, examples_section)
        
        self.assertIn("investment strategy planner", prompt)
        self.assertIn("RISK CONSTRAINTS", prompt)
        self.assertIn("TEMPLATES", prompt)
        self.assertIn("EXAMPLES", prompt)

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_plan_strategy_success(self, mock_get_registry, mock_genai):
        """Test successful strategy planning."""
        self.settings.google.api_key = "test_key"
        
        # Mock the genai client
        mock_client_instance = MagicMock()
        mock_genai.Client.return_value = mock_client_instance
        
        # Mock response structure
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_part.text = '{"strategies": [{"strategy_id": "test1"}]}'
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client_instance.models.generate_content.return_value = mock_response
        
        # Mock template registry
        mock_registry = MagicMock()
        mock_registry.get_template_examples.return_value = []
        mock_get_registry.return_value = mock_registry
        
        client = GoogleAgentClient()
        result = client.plan_strategy(mission="test mission", context={})
        
        self.assertIn("raw_text", result)
        self.assertIn("strategies", result["raw_text"])

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_plan_strategy_api_error(self, mock_get_registry, mock_genai):
        """Test strategy planning with API error."""
        self.settings.google.api_key = "test_key"
        
        # Mock the genai client to raise an exception
        mock_client_instance = MagicMock()
        mock_genai.Client.return_value = mock_client_instance
        mock_client_instance.models.generate_content.side_effect = Exception("API Error: Invalid API key")
        
        # Mock template registry
        mock_registry = MagicMock()
        mock_registry.get_template_examples.return_value = []
        mock_get_registry.return_value = mock_registry
        
        client = GoogleAgentClient()
        
        # Should raise RuntimeError for non-API-key errors
        with self.assertRaises(RuntimeError):
            client.plan_strategy(mission="test mission", context={})

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_plan_strategy_api_key_error(self, mock_get_registry, mock_genai):
        """Test strategy planning with API key error."""
        self.settings.google.api_key = "test_key"
        
        # Mock the genai client to raise an API key error
        mock_client_instance = MagicMock()
        mock_genai.Client.return_value = mock_client_instance
        mock_client_instance.models.generate_content.side_effect = Exception("API key is invalid")
        
        # Mock template registry
        mock_registry = MagicMock()
        mock_registry.get_template_examples.return_value = []
        mock_get_registry.return_value = mock_registry
        
        client = GoogleAgentClient()
        
        # Should raise ValueError for API key errors
        with self.assertRaises(ValueError):
            client.plan_strategy(mission="test mission", context={})

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_plan_strategy_invalid_response(self, mock_get_registry, mock_genai):
        """Test strategy planning with invalid response structure."""
        self.settings.google.api_key = "test_key"
        
        # Mock the genai client with invalid response structure
        mock_client_instance = MagicMock()
        mock_genai.Client.return_value = mock_client_instance
        mock_response = MagicMock()
        mock_response.candidates = []  # Empty candidates
        mock_client_instance.models.generate_content.return_value = mock_response
        
        # Mock template registry
        mock_registry = MagicMock()
        mock_registry.get_template_examples.return_value = []
        mock_get_registry.return_value = mock_registry
        
        client = GoogleAgentClient()
        
        # Should raise RuntimeError for invalid response
        with self.assertRaises(RuntimeError):
            client.plan_strategy(mission="test mission", context={})

    @patch('app.agents.google_client.genai')
    @patch('app.agents.google_client.get_template_registry')
    def test_plan_strategy_with_templates(self, mock_get_registry, mock_genai):
        """Test strategy planning includes template examples in prompt."""
        self.settings.google.api_key = "test_key"
        
        # Mock the genai client
        mock_client_instance = MagicMock()
        mock_genai.Client.return_value = mock_client_instance
        
        # Mock response
        mock_candidate = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_part.text = '{"strategies": []}'
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client_instance.models.generate_content.return_value = mock_response
        
        # Mock template registry with examples
        mock_registry = MagicMock()
        mock_registry.get_template_examples.return_value = [
            {
                "template_id": "test_template",
                "template_name": "Test Template",
                "description": "A test",
                "example_strategy": {"strategy_id": "example_1"}
            }
        ]
        mock_get_registry.return_value = mock_registry
        
        client = GoogleAgentClient()
        client.plan_strategy(mission="test mission", context={})
        
        # Verify generate_content was called
        mock_client_instance.models.generate_content.assert_called_once()
        
        # Check that the call included template information in the prompt
        call_args = mock_client_instance.models.generate_content.call_args
        prompt_text = call_args[1]["contents"][0]["parts"][0]["text"]
        self.assertIn("Template", prompt_text)


if __name__ == "__main__":
    unittest.main()

