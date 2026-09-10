"""Structured logging configuration using structlog.

Outputs JSON in production and human-readable colored output when a TTY is
detected.  Sensitive values (tokens, passwords, message bodies) are never
logged above DEBUG level.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(*, debug: bool = False) -> None:
    """Configure structlog and stdlib logging for the application.

    Args:
        debug: When ``True``, set the root log level to DEBUG and use a
            human-readable console renderer.  Otherwise, use JSON and INFO.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Shared processors applied to every log entry.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug or sys.stderr.isatty():
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers.
    for name in ("httpx", "httpcore", "neo4j", "openai", "aiogram.event"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given name."""
    return structlog.get_logger(name)
