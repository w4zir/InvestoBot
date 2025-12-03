import json
from typing import Any, Dict

from google import genai  # type: ignore[import]

from app.agents.strategy_templates import get_template_registry
from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)
settings = get_settings()


class GoogleAgentClient:
    """
    Thin wrapper around the Google GenAI / Agents client.

    This class is intentionally minimal and focused on the single use case
    of planning trading strategies. It can be extended as needed.
    """

    def __init__(self) -> None:
        if not settings.google.api_key:
            raise ValueError(
                "GOOGLE_API_KEY is not set. Please set it in your environment variables or backend/.env file. "
                "Get your API key from https://aistudio.google.com/apikey"
            )

        self._client = genai.Client(api_key=settings.google.api_key)
        self._model_name = settings.google.model

    def plan_strategy(self, mission: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the Google model/agent to propose a trading strategy.

        This returns the raw JSON-like response; higher-level parsing is
        handled by the strategy planner module.
        """
        logger.info("Calling Google Agent for strategy planning", extra={"mission": mission})

        # Get template examples for few-shot learning
        template_registry = get_template_registry()
        template_examples = template_registry.get_template_examples()
        
        # Build risk constraints section
        risk_constraints = self._build_risk_constraints_section()
        
        # Build template reference section
        template_section = self._build_template_section(template_examples)
        
        # Build few-shot examples section
        examples_section = self._build_examples_section(template_examples)
        
        # Build the complete prompt
        prompt = self._build_enhanced_prompt(risk_constraints, template_section, examples_section)

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": prompt,
                            },
                            {
                                "text": f"Mission: {mission}",
                            },
                            {
                                "text": f"Context: {context}",
                            },
                        ],
                    }
                ],
            )
        except Exception as exc:
            error_msg = str(exc)
            # Check for API key related errors
            if "API key" in error_msg or "API_KEY" in error_msg or "INVALID_ARGUMENT" in error_msg:
                logger.error("Google API key error", exc_info=True)
                raise ValueError(
                    f"Google API key is invalid or not properly configured. "
                    f"Please check your GOOGLE_API_KEY in backend/.env or environment variables. "
                    f"Get a valid API key from https://aistudio.google.com/apikey. "
                    f"Original error: {error_msg}"
                ) from exc
            # Re-raise other errors with context
            logger.error("Google API call failed", exc_info=True)
            raise RuntimeError(f"Failed to call Google Agent API: {error_msg}") from exc

        # The exact structure depends on the google-genai SDK; here we assume
        # a .text property on the first candidate, which you'll adapt as needed.
        try:
            candidate = response.candidates[0]
            text = candidate.content.parts[0].text  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to read response from Google Agent", exc_info=True)
            raise RuntimeError("Invalid response from Google Agent") from exc

        # Delegate JSON parsing to the strategy planner, which knows the schema.
        return {"raw_text": text}
    
    def _build_risk_constraints_section(self) -> str:
        """Build the risk constraints section of the prompt."""
        blacklist_str = ", ".join(settings.risk.blacklist_symbols) if settings.risk.blacklist_symbols else "none"
        
        return f"""
=== RISK CONSTRAINTS (MUST BE RESPECTED) ===

1. Position Sizing:
   - Use "fixed_fraction" position sizing
   - Fraction MUST be between 0.01 (1%) and 0.05 (5%) per trade
   - Recommended: 0.02 (2%) for most strategies
   - For intraday strategies, use smaller fractions (0.01-0.02)

2. Trade Notional Limits:
   - Maximum trade notional: ${settings.risk.max_trade_notional:,.2f}
   - Maximum portfolio exposure per symbol: {settings.risk.max_portfolio_exposure:.0%}
   - Calculate notional = quantity * price, ensure it stays within limits

3. Blacklisted Symbols (DO NOT USE):
   - {blacklist_str if blacklist_str != "none" else "No blacklisted symbols"}

4. Strategy Diversity:
   - Generate diverse strategies (different types, timeframes, indicators)
   - Avoid duplicate strategies with only minor parameter differences
   - Mix different strategy types when possible (momentum, mean-reversion, breakout)
"""
    
    def _build_template_section(self, template_examples: list) -> str:
        """Build the template reference section."""
        if not template_examples:
            return ""
        
        section = "\n=== STRATEGY TEMPLATES (OPTIONAL REFERENCE) ===\n"
        section += "You can use these templates as inspiration or generate custom strategies.\n\n"
        
        for example in template_examples:
            section += f"Template: {example['template_name']} ({example['template_id']})\n"
            section += f"Description: {example['description']}\n"
            section += f"Example strategy structure:\n"
            section += json.dumps(example['example_strategy'], indent=2)
            section += "\n\n"
        
        return section
    
    def _build_examples_section(self, template_examples: list) -> str:
        """Build the few-shot examples section."""
        if not template_examples:
            return ""
        
        section = "\n=== FEW-SHOT EXAMPLES ===\n"
        section += "Here are example strategy instantiations:\n\n"
        
        # Include 1-2 example strategies from templates
        for example in template_examples[:2]:
            section += f"Example {example['template_name']}:\n"
            section += json.dumps({"strategies": [example['example_strategy']]}, indent=2)
            section += "\n\n"
        
        return section
    
    def _build_enhanced_prompt(self, risk_constraints: str, template_section: str, examples_section: str) -> str:
        """Build the complete enhanced prompt."""
        base_prompt = """You are an investment strategy planner. You MUST output ONLY a valid JSON object (no markdown, no code blocks, no explanations).

The JSON must contain an array 'strategies', where each strategy has:
- strategy_id (string, unique identifier)
- name (optional string, descriptive name)
- description (optional string, what the strategy does)
- universe (array of strings, stock symbols to trade)
- rules (array of objects with: type ["entry"|"exit"], indicator (string), params (object))
- params (object with: position_sizing ["fixed_fraction"], fraction (float 0.01-0.05), timeframe (string like "1d", "1h"))

OUTPUT FORMAT:
{
  "strategies": [
    {
      "strategy_id": "unique_id",
      "name": "Strategy Name",
      "description": "What it does",
      "universe": ["AAPL", "MSFT"],
      "rules": [
        {"type": "entry", "indicator": "sma_cross", "params": {"fast": 20, "slow": 50}},
        {"type": "exit", "indicator": "sma_cross", "params": {"fast": 20, "slow": 50, "reverse": true}}
      ],
      "params": {"position_sizing": "fixed_fraction", "fraction": 0.02, "timeframe": "1d"}
    }
  ]
}
"""
        
        return base_prompt + risk_constraints + template_section + examples_section


_client_instance: GoogleAgentClient | None = None


def get_google_agent_client() -> GoogleAgentClient:
    """
    Return a singleton GoogleAgentClient instance.
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = GoogleAgentClient()
    return _client_instance



