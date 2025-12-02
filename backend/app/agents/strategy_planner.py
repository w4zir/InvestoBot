import json
from typing import Any, Dict, List

from app.core.logging import get_logger
from app.trading.models import StrategySpec

from .google_client import get_google_agent_client


logger = get_logger(__name__)


def generate_strategy_specs(mission: str, context: Dict[str, Any]) -> List[StrategySpec]:
    """
    Use the Google Agent to generate candidate strategy specifications.

    The agent is expected to return a JSON object with the shape:
    { "strategies": [ { ...StrategySpec fields... }, ... ] }
    """
    client = get_google_agent_client()
    raw = client.plan_strategy(mission=mission, context=context)
    raw_text = raw.get("raw_text", "")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("Agent did not return valid JSON; mission=%s", mission)
        raise

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



