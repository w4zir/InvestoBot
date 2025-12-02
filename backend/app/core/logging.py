import logging
import sys
from typing import Optional


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure application-wide logging.

    This sets a sensible default format and attaches a stream handler.
    Call this once from the FastAPI application entrypoint.
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g., by Uvicorn); don't duplicate handlers.
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Convenience function to get a named logger.
    """
    return logging.getLogger(name or __name__)



