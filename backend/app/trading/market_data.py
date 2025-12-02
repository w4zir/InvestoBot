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


def load_data(universe: List[str], start: datetime, end: datetime) -> Dict[str, List[Dict]]:
    """
    Placeholder for OHLCV data loading.

    For now, this returns synthetic data suitable for simple backtests.
    Later, wire this to Yahoo/Alpha Vantage or other data providers.
    """
    _ensure_data_dir()
    logger.info(
        "Loading synthetic market data", extra={"universe": universe, "start": start.isoformat(), "end": end.isoformat()}
    )

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



