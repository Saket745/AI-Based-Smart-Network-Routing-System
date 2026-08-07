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


def test_nroute_error_base() -> None:
    """Test that NRouteError initialized with only message sets default attributes correctly."""
    msg = "Generic error occurred"
    err = NRouteError(msg)

    assert err.message == msg
    assert str(err) == msg
    assert err.details == {}
    assert isinstance(err, Exception)


def test_nroute_error_with_details() -> None:
    """Test that NRouteError correctly stores the details dictionary."""
    msg = "Failed operation"
    details = {"node_id": "A", "code": 500}
    err = NRouteError(msg, details=details)

    assert err.message == msg
    assert err.details == details


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

    assert isinstance(NRouteError("test"), Exception)


def test_subclass_inheritance() -> None:
    """Ensure subclasses are caught by NRouteError except blocks."""
    with pytest.raises(NRouteError):
        raise TopologyError("topology failed")

    with pytest.raises(NRouteError) as exc_info:
        raise ValidationError("invalid")
    assert isinstance(exc_info.value, ValidationError)
    assert exc_info.value.message == "invalid"
