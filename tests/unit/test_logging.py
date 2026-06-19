"""Unit tests for nroute.utils.logging — configure_logging() and get_logger()."""

from __future__ import annotations

import structlog

from nroute.utils import logging as nroute_logging
from nroute.utils.logging import configure_logging, get_logger


def _reset_logging_state() -> None:
    """Reset the module-level _configured flag and structlog state between tests."""
    nroute_logging._configured = False  # type: ignore[attr-defined]
    structlog.reset_defaults()


def test_configure_logging_default_sets_configured_flag() -> None:
    """configure_logging() should set _configured = True on first call."""
    _reset_logging_state()
    assert nroute_logging._configured is False  # type: ignore[attr-defined]
    configure_logging(verbose=False, json_format=False)
    assert nroute_logging._configured is True  # type: ignore[attr-defined]


def test_configure_logging_verbose_sets_configured_flag() -> None:
    """configure_logging(verbose=True) should complete and set _configured = True."""
    _reset_logging_state()
    configure_logging(verbose=True, json_format=False)
    assert nroute_logging._configured is True  # type: ignore[attr-defined]


def test_configure_logging_json_format() -> None:
    """configure_logging(json_format=True) should complete without error."""
    _reset_logging_state()
    configure_logging(verbose=False, json_format=True)
    assert nroute_logging._configured is True  # type: ignore[attr-defined]


def test_configure_logging_idempotent() -> None:
    """Calling configure_logging() twice must be a no-op — _configured guards it."""
    _reset_logging_state()
    configure_logging(verbose=False)
    assert nroute_logging._configured is True  # type: ignore[attr-defined]

    # Reset only the structlog defaults, NOT _configured — simulate second call
    structlog.reset_defaults()
    configure_logging(verbose=True)  # Should be guarded and return immediately

    # _configured must still be True (was already set by first call)
    assert nroute_logging._configured is True  # type: ignore[attr-defined]


def test_configure_logging_each_option_no_raise() -> None:
    """All four configure_logging() invocations complete without exceptions."""
    for verbose, json_fmt in [(False, False), (False, True), (True, False), (True, True)]:
        _reset_logging_state()
        configure_logging(verbose=verbose, json_format=json_fmt)  # must not raise


def test_get_logger_returns_logger() -> None:
    """get_logger() should return a structlog BoundLogger-like object."""
    logger = get_logger("nroute.test")
    assert logger is not None
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    assert hasattr(logger, "debug")
    assert hasattr(logger, "warning")


def test_get_logger_can_log_without_error() -> None:
    """Logger returned by get_logger() must be callable for standard levels."""
    configure_logging(verbose=False)
    logger = get_logger("nroute.test.callable")
    # These must not raise
    logger.info("test info message", key="value")
    logger.debug("test debug message")
    logger.warning("test warning message")
