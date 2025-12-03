"""
Structured logging configuration with JSON formatter and context propagation.
"""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


class ContextFilter(logging.Filter):
    """Filter to add context information to log records."""

    def __init__(self):
        super().__init__()
        self.context: Dict[str, Any] = {}

    def add_context(self, key: str, value: Any) -> None:
        """Add a context key-value pair."""
        self.context[key] = value

    def remove_context(self, key: str) -> None:
        """Remove a context key."""
        self.context.pop(key, None)

    def clear_context(self) -> None:
        """Clear all context."""
        self.context.clear()

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record."""
        for key, value in self.context.items():
            setattr(record, key, value)
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add all extra fields from the record
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
            ]:
                try:
                    # Try to serialize the value
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data)


def configure_logging(
    level: int = logging.INFO,
    enable_json: bool = True,
    enable_file: bool = True,
    log_dir: Optional[Path] = None,
) -> None:
    """
    Configure application-wide logging with structured JSON output.

    Args:
        level: Logging level (default: INFO)
        enable_json: Enable JSON formatter for structured logging
        enable_file: Enable file handler for log persistence
        log_dir: Directory for log files (default: backend/logs)
    """
    root = logging.getLogger()
    
    # Clear existing handlers to avoid duplicates
    root.handlers.clear()

    # Set log level
    root.setLevel(level)

    # Add context filter
    context_filter = ContextFilter()
    root.addFilter(context_filter)

    # Console handler with human-readable format for development
    console_handler = logging.StreamHandler(sys.stdout)
    if enable_json and HAS_JSON_LOGGER:
        # Use python-json-logger if available
        console_formatter = jsonlogger.JsonFormatter(
            "%(timestamp)s %(level)s %(name)s %(message)s",
            timestamp=True,
        )
    elif enable_json:
        # Fallback to custom JSON formatter
        console_formatter = JSONFormatter()
    else:
        # Human-readable format
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    console_handler.setFormatter(console_formatter)
    root.addHandler(console_handler)

    # File handler for log persistence
    if enable_file:
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / "logs"
        else:
            log_dir = Path(log_dir)
        
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file with date suffix
        log_file = log_dir / f"app_{datetime.utcnow().strftime('%Y%m%d')}.log"
        
        file_handler = logging.FileHandler(log_file)
        if enable_json and HAS_JSON_LOGGER:
            file_formatter = jsonlogger.JsonFormatter(
                "%(timestamp)s %(level)s %(name)s %(message)s",
                timestamp=True,
            )
        elif enable_json:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        file_handler.setFormatter(file_formatter)
        root.addHandler(file_handler)

        logging.info(f"Logging to file: {log_file}")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a named logger with context support.

    Args:
        name: Logger name (default: calling module name)

    Returns:
        Logger instance
    """
    return logging.getLogger(name or __name__)


def get_context_filter() -> Optional[ContextFilter]:
    """
    Get the global context filter instance.

    Returns:
        ContextFilter instance or None if not configured
    """
    root = logging.getLogger()
    for filter_obj in root.filters:
        if isinstance(filter_obj, ContextFilter):
            return filter_obj
    return None


def add_log_context(key: str, value: Any) -> None:
    """
    Add context to all log messages.

    Args:
        key: Context key
        value: Context value
    """
    context_filter = get_context_filter()
    if context_filter:
        context_filter.add_context(key, value)


def remove_log_context(key: str) -> None:
    """
    Remove context from log messages.

    Args:
        key: Context key to remove
    """
    context_filter = get_context_filter()
    if context_filter:
        context_filter.remove_context(key)


def clear_log_context() -> None:
    """Clear all log context."""
    context_filter = get_context_filter()
    if context_filter:
        context_filter.clear_context()


class LogContext:
    """Context manager for temporary log context."""

    def __init__(self, **kwargs):
        self.context = kwargs

    def __enter__(self):
        context_filter = get_context_filter()
        if context_filter:
            for key, value in self.context.items():
                context_filter.add_context(key, value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        context_filter = get_context_filter()
        if context_filter:
            for key in self.context.keys():
                context_filter.remove_context(key)



