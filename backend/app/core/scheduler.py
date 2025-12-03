"""
Scheduler utilities for running strategies on schedule.

This module provides utilities for market hours detection and scheduling.
For Render.com deployment, we recommend using Render Cron Jobs instead of
APScheduler in the web service, but this module provides market hours utilities
that can be used by both approaches.
"""
from datetime import datetime, time
from typing import Dict, Optional
from pytz import timezone

from app.core.logging import get_logger

logger = get_logger(__name__)

# Market hours (ET timezone)
MARKET_OPEN = time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = time(16, 0)  # 4:00 PM ET
ET = timezone('US/Eastern')

# Track active runs to prevent overlapping executions (for APScheduler approach)
_active_runs: Dict[str, datetime] = {}


def is_market_open() -> bool:
    """
    Check if US stock market is currently open (weekdays 9:30 AM - 4:00 PM ET).
    
    Returns:
        True if market is open, False otherwise
    """
    now_et = datetime.now(ET)
    # Check if weekday (Monday=0, Sunday=6)
    if now_et.weekday() >= 5:  # Saturday or Sunday
        return False
    
    current_time = now_et.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def get_market_open_time_today() -> Optional[datetime]:
    """
    Get the market open time for today in ET.
    
    Returns:
        datetime for market open today, or None if market is closed today
    """
    now_et = datetime.now(ET)
    if now_et.weekday() >= 5:  # Weekend
        return None
    
    market_open = now_et.replace(
        hour=MARKET_OPEN.hour,
        minute=MARKET_OPEN.minute,
        second=0,
        microsecond=0
    )
    return market_open


def get_market_close_time_today() -> Optional[datetime]:
    """
    Get the market close time for today in ET.
    
    Returns:
        datetime for market close today, or None if market is closed today
    """
    now_et = datetime.now(ET)
    if now_et.weekday() >= 5:  # Weekend
        return None
    
    market_close = now_et.replace(
        hour=MARKET_CLOSE.hour,
        minute=MARKET_CLOSE.minute,
        second=0,
        microsecond=0
    )
    return market_close


def add_active_run(run_id: str) -> None:
    """Track an active run."""
    _active_runs[run_id] = datetime.utcnow()


def remove_active_run(run_id: str) -> None:
    """Remove a tracked run."""
    _active_runs.pop(run_id, None)


def get_active_runs() -> Dict[str, datetime]:
    """Get all currently active runs."""
    return _active_runs.copy()

