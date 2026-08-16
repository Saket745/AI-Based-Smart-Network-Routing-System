"""Unit tests for nroute custom exception hierarchy."""

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
def test_nroute_subclasses(exception_class: type[NRouteError]) -> None:
    """Test that each subclass of NRouteError inherits base attributes and behavior."""
    msg = f"{exception_class.__name__} occurred"
    details = {"context": "test"}
    err = exception_class(msg, details=details)

    assert err.message == msg
    assert err.details == details
    assert isinstance(err, NRouteError)

    # Verify we can catch the subclass using NRouteError
    try:
        raise err
    except NRouteError as caught_err:
        assert caught_err is err
        assert caught_err.message == msg
