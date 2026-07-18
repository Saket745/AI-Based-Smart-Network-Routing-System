"""Unit tests for nroute.core.query.RoutingQuery."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from nroute.core.query import RoutingQuery


def test_routing_query_minimal_valid() -> None:
    """Test minimal valid instantiation of RoutingQuery."""
    query = RoutingQuery(source="R1", destination="R2")
    assert query.source == "R1"
    assert query.destination == "R2"
    assert query.weight is None
    assert query.flow_key is None
    assert query.k is None


def test_routing_query_all_valid_fields() -> None:
    """Test instantiation with all valid parameters."""
    query = RoutingQuery(
        source="R1",
        destination="R2",
        weight="bandwidth",
        flow_key="tcp_flow_1",
        k=3,
    )
    assert query.source == "R1"
    assert query.destination == "R2"
    assert query.weight == "bandwidth"
    assert query.flow_key == "tcp_flow_1"
    assert query.k == 3


def test_routing_query_weight_as_callable() -> None:
    """Test using a custom Callable for the weight parameter."""

    def custom_weight(edge_attrs: dict[str, Any]) -> float:
        return float(edge_attrs.get("cost", 1.0)) * 2.0

    query = RoutingQuery(source="R1", destination="R2", weight=custom_weight)
    assert query.source == "R1"
    assert query.destination == "R2"
    assert callable(query.weight)

    test_attrs = {"cost": 5.0}
    assert query.weight(test_attrs) == 10.0


def test_routing_query_missing_required() -> None:
    """Test that missing required parameters raise a ValidationError."""
    with pytest.raises(ValidationError, match="source"):
        RoutingQuery(destination="R2")  # type: ignore[call-arg]

    with pytest.raises(ValidationError, match="destination"):
        RoutingQuery(source="R1")  # type: ignore[call-arg]


def test_routing_query_invalid_types() -> None:
    """Test that passing invalid types for fields raises a ValidationError."""
    # destination should not be a list or uncoercible object
    with pytest.raises(ValidationError, match="Input should be a valid string"):
        RoutingQuery(source="R1", destination=["R2"])  # type: ignore[arg-type]

    # k should be an integer
    with pytest.raises(ValidationError, match="Input should be a valid integer"):
        RoutingQuery(source="R1", destination="R2", k="not-an-int")  # type: ignore[arg-type]


def test_routing_query_arbitrary_types_allowed() -> None:
    """Test that arbitrary types are allowed for flow_key and callable weights."""

    class CustomFlowKey:
        def __init__(self, key: str) -> None:
            self.key = key

    custom_key = CustomFlowKey("secret-hash")
    query = RoutingQuery(source="R1", destination="R2", flow_key=custom_key)

    assert query.flow_key == custom_key
    assert query.flow_key.key == "secret-hash"


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


def test_routing_query_invalid_types_alternative() -> None:
    """Test that invalid types for properties raise ValidationError (alternative check)."""
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
