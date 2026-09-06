"""Structured logging configuration for the Flight Disruption Assistant.

Wraps structlog with consistent JSON formatting. Kept intentionally
small — this agent ships only the service harness (status + config),
not the full IROPS pipeline.
"""

import logging
import sys

import structlog


def configure_logger() -> None:
    """Configure structlog with JSON rendering and stdlib integration."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    """Return a module-level structlog logger."""
    return structlog.get_logger(name)
