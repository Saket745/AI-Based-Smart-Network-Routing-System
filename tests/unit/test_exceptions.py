"""Unit tests for nroute.exceptions."""

from __future__ import annotations

import pytest

from nroute.exceptions import (
    ConfigError,
    IngestionError,
    ModelError,
    NRouteError,
    RoutingError,
    SimulationError,
    TopologyError,
    ValidationError,
)


def test_nroute_error_base_initialization() -> None:
    """Test NRouteError initialization with and without details."""
    # Without details
    err = NRouteError("test message")
    assert err.message == "test message"
    assert err.details == {}
    assert str(err) == "test message"

    # With details
    details = {"code": 500, "reason": "unknown"}
    err_with_details = NRouteError("error with details", details=details)
    assert err_with_details.message == "error with details"
    assert err_with_details.details == details
    assert str(err_with_details) == "error with details"


@pytest.mark.parametrize(
    "exception_class",
    [
        TopologyError,
        IngestionError,
        RoutingError,
        SimulationError,
        ModelError,
        ConfigError,
        ValidationError,
    ],
)
def test_exception_subclasses(exception_class: type[NRouteError]) -> None:
    """Test that all subclasses inherit from NRouteError and initialize correctly."""
    message = f"test {exception_class.__name__}"
    details = {"key": "value"}

    err = exception_class(message, details=details)

    assert isinstance(err, NRouteError)
    assert isinstance(err, Exception)
    assert err.message == message
    assert err.details == details
    assert str(err) == message


def test_nroute_error_inheritance() -> None:
    """Ensure NRouteError correctly inherits from Exception."""
    with pytest.raises(NRouteError):
        raise NRouteError("test")

    with pytest.raises(Exception):
        raise NRouteError("test")


def test_subclass_inheritance() -> None:
    """Ensure subclasses are caught by NRouteError except blocks."""
    with pytest.raises(NRouteError):
        raise TopologyError("topology failed")

    try:
        raise ValidationError("invalid")
    except NRouteError as e:
        assert isinstance(e, ValidationError)
        assert e.message == "invalid"
