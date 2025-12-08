"""
External data providers for news and social media sentiment.
"""
from typing import Any, Dict, List, Optional, Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)


class NewsProvider(Protocol):
    """Interface for news data providers."""
    
    def get_news(self, symbols: List[str], timeframe_hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get news articles for given symbols.
        
        Args:
            symbols: List of stock symbols
            timeframe_hours: How many hours back to fetch news
            
        Returns:
            List of news items, each with:
            - symbol: str
            - headline: str
            - sentiment: float (-1.0 to 1.0)
            - timestamp: datetime
            - url: Optional[str]
        """
        ...


class SocialMediaProvider(Protocol):
    """Interface for social media sentiment providers."""
    
    def get_sentiment(self, symbols: List[str], timeframe_hours: int = 24) -> Dict[str, float]:
        """
        Get social media sentiment scores for given symbols.
        
        Args:
            symbols: List of stock symbols
            timeframe_hours: How many hours back to fetch sentiment
            
        Returns:
            Dict mapping symbol to sentiment score (-1.0 to 1.0)
        """
        ...


class MockNewsProvider:
    """Mock news provider for testing/development."""
    
    def get_news(self, symbols: List[str], timeframe_hours: int = 24) -> List[Dict[str, Any]]:
        """Return empty news list (mock implementation)."""
        logger.debug(f"MockNewsProvider.get_news called for {len(symbols)} symbols")
        return []


class MockSocialMediaProvider:
    """Mock social media provider for testing/development."""
    
    def get_sentiment(self, symbols: List[str], timeframe_hours: int = 24) -> Dict[str, float]:
        """Return neutral sentiment for all symbols (mock implementation)."""
        logger.debug(f"MockSocialMediaProvider.get_sentiment called for {len(symbols)} symbols")
        return {symbol: 0.0 for symbol in symbols}


# Provider registry
_news_providers: Dict[str, NewsProvider] = {
    "mock": MockNewsProvider(),
}

_social_providers: Dict[str, SocialMediaProvider] = {
    "mock": MockSocialMediaProvider(),
}


def get_news_provider(provider_name: str = "mock") -> NewsProvider:
    """
    Get a news provider by name.
    
    Args:
        provider_name: Name of the provider ("mock" is the default)
        
    Returns:
        NewsProvider instance
        
    Raises:
        ValueError: If provider not found
    """
    if provider_name not in _news_providers:
        raise ValueError(f"Unknown news provider: {provider_name}. Available: {list(_news_providers.keys())}")
    return _news_providers[provider_name]


def get_social_media_provider(provider_name: str = "mock") -> SocialMediaProvider:
    """
    Get a social media provider by name.
    
    Args:
        provider_name: Name of the provider ("mock" is the default)
        
    Returns:
        SocialMediaProvider instance
        
    Raises:
        ValueError: If provider not found
    """
    if provider_name not in _social_providers:
        raise ValueError(
            f"Unknown social media provider: {provider_name}. "
            f"Available: {list(_social_providers.keys())}"
        )
    return _social_providers[provider_name]
