from typing import Any, Dict

from google import genai  # type: ignore[import]

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

        prompt = (
            "You are an investment strategy planner. "
            "You MUST output ONLY a valid JSON object (no markdown, no code blocks, no explanations). "
            "The JSON must contain an array 'strategies', where each strategy has: "
            "strategy_id (string), name (optional string), description (optional string), "
            "universe (array of strings), rules (array of objects with type, indicator, params), "
            "and params (object with position_sizing, fraction, timeframe). "
            "Example format: {\"strategies\": [{\"strategy_id\": \"sma_cross_1\", \"name\": \"SMA Crossover\", \"universe\": [\"AAPL\"], \"rules\": [{\"type\": \"entry\", \"indicator\": \"sma_cross\", \"params\": {\"fast\": 20, \"slow\": 50}}], \"params\": {\"position_sizing\": \"fixed_fraction\", \"fraction\": 0.02, \"timeframe\": \"1d\"}}]}"
        )

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


_client_instance: GoogleAgentClient | None = None


def get_google_agent_client() -> GoogleAgentClient:
    """
    Return a singleton GoogleAgentClient instance.
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = GoogleAgentClient()
    return _client_instance



