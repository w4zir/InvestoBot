import os
from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field


class AlpacaSettings(BaseModel):
    api_key: Optional[str] = Field(default=None, alias="ALPACA_API_KEY")
    secret_key: Optional[str] = Field(default=None, alias="ALPACA_SECRET_KEY")
    base_url: AnyHttpUrl = Field(
        default="https://paper-api.alpaca.markets",
        alias="ALPACA_PAPER_BASE_URL",
    )


class GoogleAgentSettings(BaseModel):
    api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    project_id: Optional[str] = Field(default=None, alias="GOOGLE_PROJECT_ID")
    location: str = Field(default="global", alias="GOOGLE_LOCATION")
    # For google-genai style clients, you may only need model name
    model: str = Field(default="gemini-2.0-flash", alias="GOOGLE_MODEL")
    # If you later create/configure an Agent in Google AI Studio, store its ID here
    agent_id: Optional[str] = Field(default=None, alias="GOOGLE_AGENT_ID")


class RiskSettings(BaseModel):
    max_trade_notional: float = Field(default=10_000.0)
    max_portfolio_exposure: float = Field(default=0.5)
    blacklist_symbols: List[str] = Field(default_factory=list)


class DataSettings(BaseModel):
    data_dir: str = Field(default="data")
    default_universe: List[str] = Field(
        default_factory=lambda: ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]
    )
    default_lookback_days: int = 365


class AppSettings(BaseModel):
    """Top-level application settings container."""

    env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "dev"))
    debug: bool = Field(default_factory=lambda: os.getenv("APP_DEBUG", "false").lower() == "true")

    alpaca: AlpacaSettings = AlpacaSettings()
    google: GoogleAgentSettings = GoogleAgentSettings()
    risk: RiskSettings = RiskSettings()
    data: DataSettings = DataSettings()


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Return cached application settings.

    Uses environment variables to populate settings models. Values are
    cached so they can be imported and used anywhere in the app.
    """
    return AppSettings()



