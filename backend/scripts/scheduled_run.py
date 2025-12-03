"""
Scheduled strategy run script for Render.com Cron Jobs.

This script is designed to be run by Render.com Cron Jobs at scheduled times
(e.g., market open, market close, or periodic intervals).

Environment variables:
    SCHEDULED_MISSION: The mission statement for the strategy run (required)
    SCHEDULED_UNIVERSE: Comma-separated list of symbols (default: "AAPL,MSFT,GOOGL")
    SCHEDULED_EXECUTE: Whether to execute orders (default: "false")
    SCHEDULED_DATA_RANGE: Date range for backtesting (optional, uses default if not set)
    SCHEDULED_CONTEXT_JSON: Additional context as JSON string (optional)
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.scheduler import is_market_open, add_active_run, remove_active_run
from app.routes.control import is_kill_switch_enabled
from app.trading.models import StrategyRunRequest
from app.trading.orchestrator import run_strategy_run

# Configure logging
settings = get_settings()
configure_logging(level="INFO", enable_json=True, enable_file=True)
logger = get_logger(__name__)


def main():
    """Execute a scheduled strategy run."""
    run_id = f"scheduled_{int(datetime.utcnow().timestamp())}"
    
    try:
        # Check kill switch
        if is_kill_switch_enabled():
            logger.warning(
                f"Scheduled run {run_id} skipped: kill switch is enabled",
                extra={"run_id": run_id}
            )
            print(f"ERROR: Kill switch is enabled. Run {run_id} skipped.")
            sys.exit(1)
        
        # Get configuration from environment
        mission = os.getenv("SCHEDULED_MISSION")
        if not mission:
            logger.error("SCHEDULED_MISSION environment variable is required")
            print("ERROR: SCHEDULED_MISSION environment variable is required")
            sys.exit(1)
        
        # Parse universe
        universe_str = os.getenv("SCHEDULED_UNIVERSE", "AAPL,MSFT,GOOGL")
        universe = [s.strip() for s in universe_str.split(",") if s.strip()]
        
        # Parse execute flag
        should_execute = os.getenv("SCHEDULED_EXECUTE", "false").lower() == "true"
        
        # Build context
        context = {
            "universe": universe,
            "execute": should_execute
        }
        
        # Add optional data_range
        data_range = os.getenv("SCHEDULED_DATA_RANGE")
        if data_range:
            context["data_range"] = data_range
        
        # Add optional additional context from JSON
        context_json = os.getenv("SCHEDULED_CONTEXT_JSON")
        if context_json:
            try:
                additional_context = json.loads(context_json)
                context.update(additional_context)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse SCHEDULED_CONTEXT_JSON: {e}")
        
        # Log market status
        market_status = "open" if is_market_open() else "closed"
        logger.info(
            f"Starting scheduled strategy run: {run_id}",
            extra={
                "run_id": run_id,
                "mission": mission,
                "universe": universe,
                "execute": should_execute,
                "market_status": market_status
            }
        )
        
        # Track active run
        add_active_run(run_id)
        
        try:
            # Create and execute strategy run
            payload = StrategyRunRequest(mission=mission, context=context)
            response = run_strategy_run(payload)
            
            logger.info(
                f"Scheduled run completed successfully: {run_id}",
                extra={
                    "run_id": response.run_id,
                    "candidates": len(response.candidates),
                    "mission": response.mission
                }
            )
            
            print(f"SUCCESS: Run {response.run_id} completed with {len(response.candidates)} candidates")
            
        finally:
            remove_active_run(run_id)
            
    except ValueError as e:
        # Kill switch or validation error
        logger.error(f"Scheduled run {run_id} failed: {e}", exc_info=True)
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scheduled run {run_id} failed with unexpected error", exc_info=True)
        print(f"ERROR: Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

