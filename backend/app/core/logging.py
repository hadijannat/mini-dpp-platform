"""
Structured logging configuration using structlog.
Provides JSON-formatted logs for production and human-readable logs for development.
"""

import logging
import sys
from typing import cast

import structlog
from structlog.types import Processor

from app.core.config import get_settings


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    In development mode, logs are formatted for human readability.
    In production mode, logs are JSON-formatted for log aggregation systems.
    """
    settings = get_settings()

    # Shared processors for both modes
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.environment == "development":
        # Development: Human-readable colored output
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
    else:
        # Production: JSON output for log aggregation
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance with the given name."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
