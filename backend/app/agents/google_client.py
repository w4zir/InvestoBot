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
            logger.warning("GOOGLE_API_KEY is not set; agent calls will fail at runtime.")

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
            "Output a JSON object containing an array 'strategies', where each "
            "strategy follows the provided schema (rules, params, timeframe, universe). "
            "Do not include any prose outside the JSON."
        )

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



