from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _ensure_data_dir() -> Path:
    path = Path(settings.data.data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_data_yahoo(universe: List[str], start: datetime, end: datetime) -> Dict[str, List[Dict]]:
    """
    Load OHLCV data from Yahoo Finance using yfinance.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Install with: pip install yfinance")
        raise

    data: Dict[str, List[Dict]] = {}
    for symbol in universe:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start.date(), end=end.date())
            if df.empty:
                logger.warning(f"No data found for {symbol} in date range")
                continue

            series: List[Dict] = []
            for idx, row in df.iterrows():
                # Convert pandas Timestamp to datetime
                ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else datetime.fromisoformat(str(idx))
                candle = {
                    "timestamp": ts,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
                series.append(candle)
            data[symbol] = series
            logger.info(f"Loaded {len(series)} bars for {symbol} from Yahoo Finance")
        except Exception as e:
            logger.error(f"Failed to load data for {symbol} from Yahoo Finance: {e}", exc_info=True)
            # Continue with other symbols

    return data


def _load_data_synthetic(universe: List[str], start: datetime, end: datetime) -> Dict[str, List[Dict]]:
    """
    Generate synthetic OHLCV data for testing.
    """
    data: Dict[str, List[Dict]] = {}
    days = (end - start).days or 1

    for symbol in universe:
        series: List[Dict] = []
        price = 100.0
        for i in range(days):
            ts = start + timedelta(days=i)
            # Very naive random walk-ish synthetic prices
            price *= 1.0 + (0.001 if i % 2 == 0 else -0.001)
            candle = {
                "timestamp": ts,
                "open": price * 0.99,
                "high": price * 1.01,
                "low": price * 0.98,
                "close": price,
                "volume": 1_000_000,
            }
            series.append(candle)
        data[symbol] = series

    return data


def load_data(universe: List[str], start: datetime, end: datetime, use_cache: bool = True) -> Dict[str, List[Dict]]:
    """
    Load OHLCV data from configured source (synthetic or Yahoo Finance).
    Uses data manager for caching if enabled.

    Args:
        universe: List of symbols to load
        start: Start datetime
        end: End datetime
        use_cache: Whether to use cache (default: True)

    Returns:
        Dictionary mapping symbol to list of OHLCV bars
    """
    _ensure_data_dir()
    source = settings.data.source.lower()

    logger.info(
        f"Loading market data from {source}",
        extra={"universe": universe, "start": start.isoformat(), "end": end.isoformat(), "source": source},
    )

    # Try to use data manager for caching
    if use_cache and settings.data.cache_enabled:
        try:
            from app.trading.data_manager import get_data_manager
            
            data_manager = get_data_manager()
            
            # Define data loader function
            def _load_from_source(symbols: List[str], start_dt: datetime, end_dt: datetime) -> Dict[str, List[Dict]]:
                if source == "yahoo":
                    return _load_data_yahoo(symbols, start_dt, end_dt)
                else:
                    return _load_data_synthetic(symbols, start_dt, end_dt)
            
            # Use data manager to load (with caching)
            return data_manager.refresh_data(
                symbols=universe,
                start_date=start,
                end_date=end,
                force=False,
                data_loader_func=_load_from_source,
            )
        except Exception as e:
            logger.warning(f"Data manager failed, falling back to direct load: {e}", exc_info=True)
            # Fall through to direct load
    
    # Direct load (no caching or cache disabled)
    if source == "yahoo":
        return _load_data_yahoo(universe, start, end)
    else:
        return _load_data_synthetic(universe, start, end)



