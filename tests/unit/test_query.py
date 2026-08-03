"""Unit tests for the RoutingQuery parameter object."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from nroute.core.query import RoutingQuery


def test_routing_query_valid_defaults() -> None:
    """Test valid instantiation with defaults."""
    query = RoutingQuery(source="A", destination="B")
    assert query.source == "A"
    assert query.destination == "B"
    assert query.weight is None
    assert query.flow_key is None
    assert query.k is None


def test_routing_query_valid_with_values() -> None:
    """Test valid instantiation with all custom values."""

    def dummy_weight(edge_attrs: dict[str, Any]) -> float:
        return float(edge_attrs.get("latency", 1.0))

    query = RoutingQuery(
        source="A",
        destination="B",
        weight=dummy_weight,
        flow_key="some-flow-key",
        k=5,
    )
    assert query.source == "A"
    assert query.destination == "B"
    assert query.weight == dummy_weight
    assert query.flow_key == "some-flow-key"
    assert query.k == 5


def test_routing_query_string_weight() -> None:
    """Test valid instantiation with a string weight attribute name."""
    query = RoutingQuery(
        source="A",
        destination="B",
        weight="latency",
    )
    assert query.weight == "latency"


def test_routing_query_missing_required_fields() -> None:
    """Test that missing required fields raises a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        RoutingQuery(destination="B")  # type: ignore[call-arg]
    assert "source" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        RoutingQuery(source="A")  # type: ignore[call-arg]
    assert "destination" in str(exc_info.value)


def test_routing_query_invalid_types() -> None:
    """Test that invalid types for properties raise ValidationError."""
    # k must be an integer (or coercible to integer under Pydantic rules)
    # Pydantic is smart enough to coerce "5" to 5, but not "abc"
    with pytest.raises(ValidationError) as exc_info:
        RoutingQuery(source="A", destination="B", k="abc")  # type: ignore[arg-type]
    assert "k" in str(exc_info.value)


def test_routing_query_arbitrary_types() -> None:
    """Test that arbitrary types are allowed due to config settings."""

    class CustomObject:
        pass

    obj = CustomObject()
    query = RoutingQuery(
        source="A",
        destination="B",
        flow_key=obj,
    )
    assert query.flow_key is obj
