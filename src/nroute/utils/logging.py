"""nroute logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from structlog.types import FilteringBoundLogger

_configured: bool = False


def configure_logging(
    verbose: bool = False,
    quiet: bool = False,
    json_format: bool = False,
    colors: bool = True,
    log_level_override: str | None = None,
) -> None:
    """
    Configure global structlog logging.

    Args:
        verbose: If True, set the logging level to DEBUG.
        quiet: If True, set the logging level to ERROR.
        json_format: If True, output in JSON format. Otherwise, use human-readable console format.
        colors: If True, enable colored output.
        log_level_override: Optional custom log level override string.
    """
    global _configured
    if _configured:
        return

    # Resolve logging level
    if quiet:
        log_level = logging.ERROR
    elif verbose:
        log_level = logging.DEBUG
    elif log_level_override:
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        log_level = level_map.get(log_level_override.upper(), logging.INFO)
    else:
        log_level = logging.INFO

    # Configure stdlib logging root logger
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stderr,
    )

    processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        import os

        env_no_color = "NO_COLOR" in os.environ
        use_colors = colors and not env_no_color
        processors.append(structlog.dev.ConsoleRenderer(colors=use_colors))

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> FilteringBoundLogger:
    """
    Get a logger instance with the given name.

    Args:
        name: The name of the logger (typically __name__).
    """
    import typing

    return typing.cast("FilteringBoundLogger", structlog.get_logger(name))
