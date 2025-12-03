import json
import re
from typing import Any, Dict, List, Set

from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading.models import StrategySpec

from .google_client import get_google_agent_client


logger = get_logger(__name__)
settings = get_settings()


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
            strategy = StrategySpec.model_validate(item)
            # Validate risk constraints
            validation_errors = _validate_strategy_constraints(strategy)
            if validation_errors:
                logger.warning(
                    "Strategy %s (%s) failed validation: %s",
                    i,
                    strategy.strategy_id,
                    "; ".join(validation_errors)
                )
                # Try to fix common issues
                strategy = _fix_strategy_constraints(strategy)
            strategies.append(strategy)
        except Exception as exc:
            logger.warning(
                "Failed to validate strategy %s from agent response: %s", i, exc
            )

    if not strategies:
        raise ValueError("No valid strategies produced by agent")
    
    # Check strategy diversity
    _ensure_strategy_diversity(strategies)
    
    logger.info(
        "Generated %d strategies after validation",
        len(strategies),
        extra={"strategy_count": len(strategies)}
    )

    return strategies


def _validate_strategy_constraints(strategy: StrategySpec) -> List[str]:
    """
    Validate a strategy against risk constraints.
    
    Returns list of validation error messages (empty if valid).
    """
    errors: List[str] = []
    
    # Check position sizing fraction
    if strategy.params.fraction is not None:
        if strategy.params.fraction < 0.01:
            errors.append(f"Position sizing fraction too small: {strategy.params.fraction} (minimum 0.01)")
        elif strategy.params.fraction > 0.05:
            errors.append(f"Position sizing fraction too large: {strategy.params.fraction} (maximum 0.05)")
    
    # Check for blacklisted symbols
    blacklist = set(settings.risk.blacklist_symbols)
    blacklisted_in_universe = [s for s in strategy.universe if s in blacklist]
    if blacklisted_in_universe:
        errors.append(f"Universe contains blacklisted symbols: {blacklisted_in_universe}")
    
    # Check universe is not empty
    if not strategy.universe:
        errors.append("Universe is empty")
    
    # Check rules are not empty
    if not strategy.rules:
        errors.append("Rules list is empty")
    
    return errors


def _fix_strategy_constraints(strategy: StrategySpec) -> StrategySpec:
    """
    Attempt to fix common constraint violations in a strategy.
    
    Returns a corrected strategy (may be the same if no fixes needed).
    """
    # Fix position sizing fraction if out of bounds
    if strategy.params.fraction is not None:
        if strategy.params.fraction < 0.01:
            logger.info(f"Fixing fraction {strategy.params.fraction} -> 0.01")
            strategy.params.fraction = 0.01
        elif strategy.params.fraction > 0.05:
            logger.info(f"Fixing fraction {strategy.params.fraction} -> 0.05")
            strategy.params.fraction = 0.05
    
    # Remove blacklisted symbols from universe
    blacklist = set(settings.risk.blacklist_symbols)
    original_universe = strategy.universe.copy()
    strategy.universe = [s for s in strategy.universe if s not in blacklist]
    if len(strategy.universe) < len(original_universe):
        removed = set(original_universe) - set(strategy.universe)
        logger.info(f"Removed blacklisted symbols from universe: {removed}")
        # If universe becomes empty, add a default symbol
        if not strategy.universe:
            default_symbols = settings.data.default_universe
            strategy.universe = [s for s in default_symbols if s not in blacklist][:1]
            logger.info(f"Added default symbol to empty universe: {strategy.universe}")
    
    return strategy


def _ensure_strategy_diversity(strategies: List[StrategySpec]) -> None:
    """
    Check strategy diversity and log warnings if strategies are too similar.
    
    This is a soft check - it logs warnings but doesn't remove strategies.
    """
    if len(strategies) < 2:
        return
    
    # Check for duplicate strategy IDs
    strategy_ids: Set[str] = set()
    for strategy in strategies:
        if strategy.strategy_id in strategy_ids:
            logger.warning(f"Duplicate strategy_id found: {strategy.strategy_id}")
        strategy_ids.add(strategy.strategy_id)
    
    # Check for very similar strategies (same rules, similar params)
    for i, strategy1 in enumerate(strategies):
        for j, strategy2 in enumerate(strategies[i+1:], start=i+1):
            similarity = _calculate_strategy_similarity(strategy1, strategy2)
            if similarity > 0.9:  # 90% similar
                logger.warning(
                    f"Strategies {strategy1.strategy_id} and {strategy2.strategy_id} "
                    f"are very similar (similarity: {similarity:.2f})"
                )


def _calculate_strategy_similarity(strategy1: StrategySpec, strategy2: StrategySpec) -> float:
    """
    Calculate similarity score between two strategies (0.0 to 1.0).
    
    Simple heuristic based on:
    - Same universe
    - Same number of rules
    - Same rule types and indicators
    - Similar params
    """
    similarity = 0.0
    
    # Universe similarity
    if set(strategy1.universe) == set(strategy2.universe):
        similarity += 0.3
    elif set(strategy1.universe) & set(strategy2.universe):
        similarity += 0.15
    
    # Rules similarity
    if len(strategy1.rules) == len(strategy2.rules):
        similarity += 0.2
        # Check if rule types match
        rule_types1 = [r.type for r in strategy1.rules]
        rule_types2 = [r.type for r in strategy2.rules]
        if rule_types1 == rule_types2:
            similarity += 0.3
            # Check indicators
            indicators1 = [r.indicator for r in strategy1.rules]
            indicators2 = [r.indicator for r in strategy2.rules]
            if indicators1 == indicators2:
                similarity += 0.2
    
    return min(similarity, 1.0)



