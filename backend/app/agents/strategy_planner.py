import json
import re
from typing import Any, Dict, List

from app.core.logging import get_logger
from app.trading.models import StrategySpec

from .google_client import get_google_agent_client


logger = get_logger(__name__)


def _extract_json_from_text(text: str) -> str:
    """
    Extract JSON from text that might contain markdown code blocks or extra prose.
    
    Handles cases like:
    - ```json\n{...}\n```
    - ```\n{...}\n```
    - Plain JSON: {...}
    - Text before/after JSON
    """
    if not text:
        return ""
    
    # Try to find JSON in markdown code blocks first
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    
    # Try to find JSON object by matching braces (handles nested structures)
    # Find the first { and then match to its closing }
    start_idx = text.find('{')
    if start_idx == -1:
        return text.strip()
    
    brace_count = 0
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                # Found complete JSON object
                return text[start_idx:i+1]
    
    # If no complete match, try the original text
    return text.strip()


def generate_strategy_specs(mission: str, context: Dict[str, Any]) -> List[StrategySpec]:
    """
    Use the Google Agent to generate candidate strategy specifications.

    The agent is expected to return a JSON object with the shape:
    { "strategies": [ { ...StrategySpec fields... }, ... ] }
    """
    client = get_google_agent_client()
    raw = client.plan_strategy(mission=mission, context=context)
    raw_text = raw.get("raw_text", "")

    if not raw_text:
        logger.error("Agent returned empty response; mission=%s", mission)
        raise ValueError("Agent returned empty response")

    # Log the raw response for debugging (first 500 chars)
    logger.debug("Raw agent response (first 500 chars): %s", raw_text[:500])

    # Extract JSON from potentially formatted text
    json_text = _extract_json_from_text(raw_text)
    
    if not json_text:
        logger.error("Could not extract JSON from agent response; mission=%s", mission)
        logger.error("Full response: %s", raw_text)
        raise ValueError("Could not extract JSON from agent response")

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.error("Agent did not return valid JSON; mission=%s", mission)
        logger.error("Extracted JSON text: %s", json_text[:500])
        logger.error("JSON decode error: %s", str(e))
        raise ValueError(f"Agent response is not valid JSON: {str(e)}") from e

    strategies_data = payload.get("strategies", [])
    if not isinstance(strategies_data, list):
        raise ValueError("Expected 'strategies' to be a list in agent response")

    strategies: List[StrategySpec] = []
    for i, item in enumerate(strategies_data):
        try:
            strategies.append(StrategySpec.model_validate(item))
        except Exception as exc:
            logger.warning(
                "Failed to validate strategy %s from agent response: %s", i, exc
            )

    if not strategies:
        raise ValueError("No valid strategies produced by agent")

    return strategies



