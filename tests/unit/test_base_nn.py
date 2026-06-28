"""Unit tests for the BaseNNRouter abstract class."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.ml.features.extractor import BaseFeatureExtractor
from nroute.routing.base_nn import BaseNNRouter


class MockNNRouter(BaseNNRouter):
    """Concrete implementation of BaseNNRouter for testing."""

    def __init__(self, next_hops: dict[tuple[str, str], str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.next_hops = next_hops or {}

    def predict_next_hop(
        self,
        features: Any,
        current_node: str,
        destination: str,
        topology: Topology,
    ) -> str:
        return self.next_hops.get((current_node, destination), "INVALID")


def test_base_nn_router_happy_path() -> None:
    """Test successful path computation with valid next-hops."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B")
    topo.add_edge("B", "C")

    router = MockNNRouter(next_hops={("A", "C"): "B", ("B", "C"): "C"})
    path = router.compute_path(topo, "A", "C")
    assert path == ["A", "B", "C"]


def test_base_nn_router_missing_nodes() -> None:
    """Test handling of source or destination nodes missing from the topology."""
    topo = Topology()
    topo.add_node("A")
    router = MockNNRouter()

    with pytest.raises(RoutingError, match="Source node 'X' is down or does not exist"):
        router.compute_path(topo, "X", "A")

    with pytest.raises(RoutingError, match="Destination node 'Y' is down or does not exist"):
        router.compute_path(topo, "A", "Y")


def test_base_nn_router_source_is_destination() -> None:
    """Test path computation when source and destination are the same."""
    topo = Topology()
    topo.add_node("A")
    router = MockNNRouter()
    assert router.compute_path(topo, "A", "A") == ["A"]


def test_base_nn_router_prediction_failure() -> None:
    """Test handling of exceptions during next-hop prediction."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B")

    class FailingRouter(BaseNNRouter):
        def predict_next_hop(
            self, features: Any, current_node: str, destination: str, topology: Topology
        ) -> str:
            raise ValueError("Model error")

    router = FailingRouter()
    with pytest.raises(RoutingError, match="NN router next-hop prediction failed: Model error"):
        router.compute_path(topo, "A", "B")


def test_base_nn_router_invalid_next_hop() -> None:
    """Test handling when predicted next-hop is not a neighbor in the topology."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B")
    # A is not connected to C

    router = MockNNRouter(next_hops={("A", "C"): "C"})
    with pytest.raises(RoutingError, match="NN router predicted invalid next-hop 'C' from 'A'"):
        router.compute_path(topo, "A", "C")


def test_base_nn_router_loop_detection() -> None:
    """Test that loops in predicted paths are detected and an error is raised."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B")
    topo.add_edge("B", "A")
    topo.add_edge("B", "C")

    # A -> B -> A loop while trying to reach C
    router = MockNNRouter(next_hops={("A", "C"): "B", ("B", "C"): "A"})
    with pytest.raises(RoutingError, match="NN router predicted next-hop 'A' causing a loop"):
        router.compute_path(topo, "A", "C")


def test_base_nn_router_feature_extractor() -> None:
    """Test integration with a feature extractor."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B")

    mock_extractor = MagicMock(spec=BaseFeatureExtractor)
    mock_features = MagicMock()
    mock_extractor.extract_features.return_value = mock_features

    class FeatureCheckingRouter(BaseNNRouter):
        def predict_next_hop(
            self, features: Any, current_node: str, destination: str, topology: Topology
        ) -> str:
            assert features == mock_features
            return destination

    router = FeatureCheckingRouter(feature_extractor=mock_extractor)
    router.compute_path(topo, "A", "B")
    mock_extractor.extract_features.assert_called_once_with(topo)


def test_base_nn_router_node_down() -> None:
    """Test that nodes with 'down' status are excluded from routing."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B")

    topo.set_node_down("B")
    router = MockNNRouter(next_hops={("A", "B"): "B"})
    with pytest.raises(RoutingError, match="Destination node 'B' is down"):
        router.compute_path(topo, "A", "B")


def test_base_nn_router_edge_down() -> None:
    """Test that edges with 'down' status are excluded from routing."""
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B")
    topo.add_edge("B", "C")

    topo.set_link_down("B", "C")
    router = MockNNRouter(next_hops={("A", "C"): "B", ("B", "C"): "C"})
    with pytest.raises(RoutingError, match="NN router predicted invalid next-hop 'C' from 'B'"):
        router.compute_path(topo, "A", "C")
