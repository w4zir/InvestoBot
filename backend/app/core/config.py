import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseModel, Field

# Load environment variables from .env file
# Try backend/.env first, then backend/app/.env
env_path = Path(__file__).parent.parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"

if env_path.exists():
    load_dotenv(env_path)
else:
    # If no .env file found, try loading from current directory (for when running from backend/)
    load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)


class AlpacaSettings(BaseModel):
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ALPACA_API_KEY"))
    secret_key: Optional[str] = Field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY"))
    base_url: AnyHttpUrl = Field(
        default_factory=lambda: os.getenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")
    )


class GoogleAgentSettings(BaseModel):
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY"))
    project_id: Optional[str] = Field(default_factory=lambda: os.getenv("GOOGLE_PROJECT_ID"))
    location: str = Field(default_factory=lambda: os.getenv("GOOGLE_LOCATION", "global"))
    # For google-genai style clients, you may only need model name
    model: str = Field(default_factory=lambda: os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"))
    # If you later create/configure an Agent in Google AI Studio, store its ID here
    agent_id: Optional[str] = Field(default_factory=lambda: os.getenv("GOOGLE_AGENT_ID"))


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
    source: str = Field(default_factory=lambda: os.getenv("DATA_SOURCE", "synthetic"))  # "synthetic" or "yahoo"


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



