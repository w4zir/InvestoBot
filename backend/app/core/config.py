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
    # Token budget and tracking
    token_budget_limit: Optional[float] = Field(default_factory=lambda: float(os.getenv("GOOGLE_TOKEN_BUDGET_LIMIT", "0")) if os.getenv("GOOGLE_TOKEN_BUDGET_LIMIT") else None)
    prompt_version: str = Field(default_factory=lambda: os.getenv("GOOGLE_PROMPT_VERSION", "v1"))


class OpenAISettings(BaseModel):
    """OpenAI API settings."""
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
    token_budget_limit: Optional[float] = Field(default_factory=lambda: float(os.getenv("OPENAI_TOKEN_BUDGET_LIMIT", "0")) if os.getenv("OPENAI_TOKEN_BUDGET_LIMIT") else None)


class AnthropicSettings(BaseModel):
    """Anthropic API settings."""
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"))
    token_budget_limit: Optional[float] = Field(default_factory=lambda: float(os.getenv("ANTHROPIC_TOKEN_BUDGET_LIMIT", "0")) if os.getenv("ANTHROPIC_TOKEN_BUDGET_LIMIT") else None)


class LLMProviderSettings(BaseModel):
    """LLM provider configuration settings."""
    provider_primary: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER_PRIMARY", "google"))  # "google", "openai", "anthropic"
    provider_failover_enabled: bool = Field(default_factory=lambda: os.getenv("LLM_PROVIDER_FAILOVER_ENABLED", "false").lower() == "true")
    provider_failover_list: List[str] = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER_FAILOVER_LIST", "").split(",") if os.getenv("LLM_PROVIDER_FAILOVER_LIST") else []
    )  # List of backup provider names


class RiskSettings(BaseModel):
    max_trade_notional: float = Field(default=10_000.0)
    max_portfolio_exposure: float = Field(default=0.5)
    max_position_per_symbol: float = Field(default=0.2)  # Max 20% of portfolio per symbol
    max_drawdown_threshold: float = Field(default=0.15)  # 15% max drawdown before blocking trades
    max_correlation_exposure: float = Field(default=0.4)  # Max 40% exposure to correlated assets
    correlation_threshold: float = Field(default=0.7)  # Correlation threshold for grouping
    min_avg_volume: float = Field(default=1_000_000)  # Min average daily volume in dollars
    min_volume_ratio: float = Field(default=0.1)  # Max order size / ADV ratio (10%)
    var_confidence_level: float = Field(default=0.95)  # 95% VaR confidence level
    var_horizon_days: int = Field(default=1)  # 1-day VaR horizon
    blacklist_symbols: List[str] = Field(default_factory=list)


class DataSettings(BaseModel):
    data_dir: str = Field(default="data")
    default_universe: List[str] = Field(
        default_factory=lambda: ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]
    )
    default_lookback_days: int = 365
    source: str = Field(default_factory=lambda: os.getenv("DATA_SOURCE", "synthetic"))  # "synthetic" or "yahoo"
    default_timeframe: str = Field(default_factory=lambda: os.getenv("DATA_DEFAULT_TIMEFRAME", "1d"))  # "1m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "1wk", "1mo", "3mo"
    # Data management settings
    cache_enabled: bool = Field(default_factory=lambda: os.getenv("DATA_CACHE_ENABLED", "true").lower() == "true")
    cache_ttl_hours: int = Field(default_factory=lambda: int(os.getenv("DATA_CACHE_TTL_HOURS", "24")))
    quality_checks_enabled: bool = Field(default_factory=lambda: os.getenv("DATA_QUALITY_CHECKS_ENABLED", "true").lower() == "true")
    refresh_schedule: Optional[str] = Field(default_factory=lambda: os.getenv("DATA_REFRESH_SCHEDULE", "0 2 * * *"))  # Daily at 2 AM
    file_format: str = Field(default_factory=lambda: os.getenv("DATA_FILE_FORMAT", "json"))  # "json" or "parquet"


class BrokerSettings(BaseModel):
    """Broker configuration settings."""
    broker_type: str = Field(default_factory=lambda: os.getenv("BROKER_TYPE", "alpaca"))  # "alpaca", "ib", etc.
    broker_primary: str = Field(default_factory=lambda: os.getenv("BROKER_PRIMARY", "alpaca"))  # Primary broker name
    broker_failover_enabled: bool = Field(default_factory=lambda: os.getenv("BROKER_FAILOVER_ENABLED", "false").lower() == "true")
    broker_failover_list: List[str] = Field(
        default_factory=lambda: os.getenv("BROKER_FAILOVER_LIST", "").split(",") if os.getenv("BROKER_FAILOVER_LIST") else []
    )  # List of backup broker names


class ExternalDataSettings(BaseModel):
    """External data provider settings for news and social media."""
    news_provider: str = Field(default_factory=lambda: os.getenv("NEWS_PROVIDER", "mock"))  # "mock", "newsapi", "alpha_vantage"
    social_media_provider: str = Field(default_factory=lambda: os.getenv("SOCIAL_MEDIA_PROVIDER", "mock"))  # "mock", "twitter", "reddit"
    enable_news_integration: bool = Field(default_factory=lambda: os.getenv("ENABLE_NEWS_INTEGRATION", "true").lower() == "true")
    enable_social_integration: bool = Field(default_factory=lambda: os.getenv("ENABLE_SOCIAL_INTEGRATION", "true").lower() == "true")
    # API keys for future providers
    newsapi_key: Optional[str] = Field(default_factory=lambda: os.getenv("NEWSAPI_KEY"))
    twitter_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("TWITTER_API_KEY"))
    reddit_client_id: Optional[str] = Field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID"))
    reddit_client_secret: Optional[str] = Field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET"))


class AppSettings(BaseModel):
    """Top-level application settings container."""

    env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "dev"))
    debug: bool = Field(default_factory=lambda: os.getenv("APP_DEBUG", "false").lower() == "true")

    alpaca: AlpacaSettings = AlpacaSettings()
    google: GoogleAgentSettings = GoogleAgentSettings()
    openai: OpenAISettings = OpenAISettings()
    anthropic: AnthropicSettings = AnthropicSettings()
    llm_provider: LLMProviderSettings = LLMProviderSettings()
    risk: RiskSettings = RiskSettings()
    data: DataSettings = DataSettings()
    broker: BrokerSettings = BrokerSettings()
    external_data: ExternalDataSettings = ExternalDataSettings()


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Return cached application settings.

    Uses environment variables to populate settings models. Values are
    cached so they can be imported and used anywhere in the app.
    """
    return AppSettings()



