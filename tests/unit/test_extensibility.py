"""Unit tests for nroute extensibility APIs, custom loaders, and GNN feature builders."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from click.testing import CliRunner

from nroute.cli.main import cli
from nroute.core.config import NRouteConfig
from nroute.core.topology import Topology
from nroute.exceptions import RoutingError
from nroute.ml.features import DefaultGraphFeatureExtractor
from nroute.routing import get_router
from nroute.routing.base_nn import BaseNNRouter
from nroute.utils.loader import load_custom_class

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]


def test_loader_valid_and_invalid() -> None:
    """Test loading custom classes dynamically from files and module paths."""
    # Create temporary python file with a router class
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "my_custom_module.py"
        file_path.write_text(
            """
class CustomTestRouter:
    def __init__(self, topology=None):
        self.topology = topology
    def compute_path(self, topology, source, destination, weight=None):
        return [source, destination]
"""
        )

        # Valid loading
        cls = load_custom_class(f"{file_path}:CustomTestRouter", allow_unsafe=True)
        assert cls.__name__ == "CustomTestRouter"
        router = cls()
        assert router.compute_path(None, "A", "B") == ["A", "B"]

        # Invalid subclass validation
        from nroute.routing.base import BaseRouter

        with pytest.raises(TypeError, match="does not inherit from"):
            load_custom_class(
                f"{file_path}:CustomTestRouter",
                expected_superclass=BaseRouter,
                allow_unsafe=True,
            )

        # Invalid format (no colon)
        with pytest.raises(ValueError, match="Expected format"):
            load_custom_class(str(file_path))

        # Invalid class name
        with pytest.raises(ImportError, match="not found"):
            load_custom_class(
                f"{file_path}:NonexistentClass", allow_unsafe=True
            )

        # Invalid file path
        with pytest.raises(ImportError, match="not found"):
            load_custom_class("nonexistent_file.py:SomeClass", allow_unsafe=True)


def test_config_custom_routers_resolution(monkeypatch: Any) -> None:
    """Test that get_router resolves custom routers configured in yaml/config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "configured_router.py"
        file_path.write_text(
            """
from nroute.routing.base import BaseRouter
class ConfiguredRouter(BaseRouter):
    def compute_path(self, topology, source, destination, weight=None):
        return [source, "via-config", destination]
"""
        )

        # Mock config loading to return a config with custom_routers mapping
        cfg = NRouteConfig()
        cfg.custom_routers["my-config-router"] = f"{file_path}:ConfiguredRouter"

        # Monkeypatch load_config to return our mocked config
        import nroute.core.config

        monkeypatch.setattr(
            nroute.core.config, "load_config", lambda *args, **kwargs: cfg
        )

        # get_router should resolve and load it
        router = get_router("my-config-router", allow_unsafe=True)
        assert router.__class__.__name__ == "ConfiguredRouter"
        assert router.compute_path(Topology(), "A", "B") == ["A", "via-config", "B"]


def test_default_graph_feature_extractor() -> None:
    """Test GNN graph feature extraction shapes and data types."""
    topo = Topology()
    topo.add_node("A", capacity=1000.0)
    topo.add_node("B", capacity=2000.0)
    topo.add_edge(
        "A", "B", bandwidth=1000.0, latency=5.0, utilization=0.25, packet_loss=0.01
    )

    # 1. NumPy Extractor
    extractor = DefaultGraphFeatureExtractor(use_pytorch=False)
    features = extractor.extract_features(topo)

    # Node features: N x 3 (capacity, status, degree)
    assert isinstance(features["node_features"], np.ndarray)
    assert features["node_features"].shape == (2, 3)
    # A (capacity 1.0, status 1.0, degree 1.0)
    assert np.allclose(features["node_features"][0], [1.0, 1.0, 1.0])
    # B (capacity 2.0, status 1.0, degree 0.0)
    assert np.allclose(features["node_features"][1], [2.0, 1.0, 0.0])

    # Edge index: 2 x E
    assert isinstance(features["edge_index"], np.ndarray)
    assert features["edge_index"].shape == (2, 1)
    assert np.array_equal(features["edge_index"], [[0], [1]])

    # Edge features: E x 5 (bandwidth, latency, utilization, packet_loss, status)
    assert isinstance(features["edge_features"], np.ndarray)
    assert features["edge_features"].shape == (1, 5)
    assert np.allclose(features["edge_features"][0], [1.0, 0.05, 0.25, 0.01, 1.0])

    # 2. PyTorch Extractor
    if torch is not None:
        torch_extractor = DefaultGraphFeatureExtractor(use_pytorch=True)
        torch_features = torch_extractor.extract_features(topo)

        assert isinstance(torch_features["node_features"], torch.Tensor)
        assert isinstance(torch_features["edge_index"], torch.Tensor)
        assert isinstance(torch_features["edge_features"], torch.Tensor)
        assert torch_features["node_features"].shape == (2, 3)
        assert torch_features["edge_index"].shape == (2, 1)


def test_base_nn_router_subclass() -> None:
    """Test subclassing BaseNNRouter and its routing loop execution/validations."""

    class MockGNNRouter(BaseNNRouter):
        def predict_next_hop(
            self, features: Any, current_node: str, destination: str, topology: Topology
        ) -> str:
            # Hardcode simple next hop hops: A -> B -> C
            hops = {"A": "B", "B": "C"}
            return hops.get(current_node, destination)

    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B")
    topo.add_edge("B", "C")

    # Valid route A -> C
    router = MockGNNRouter()
    path = router.compute_path(topo, "A", "C")
    assert path == ["A", "B", "C"]

    # Test loop detection
    topo_loop = Topology()
    topo_loop.add_node("A")
    topo_loop.add_node("B")
    topo_loop.add_node("C")
    topo_loop.add_edge("A", "B")
    topo_loop.add_edge("B", "C")
    topo_loop.add_edge("B", "A")  # Allow pathing B -> A to test loop detection

    class LoopNNRouter(BaseNNRouter):
        def predict_next_hop(
            self, features: Any, current_node: str, destination: str, topology: Topology
        ) -> str:
            # Forces A -> B -> A loop
            return "A" if current_node == "B" else "B"

    loop_router = LoopNNRouter()
    with pytest.raises(RoutingError, match="causing a loop"):
        loop_router.compute_path(topo_loop, "A", "C")

    # Test invalid next-hop (no edge)
    class DisconnectedNNRouter(BaseNNRouter):
        def predict_next_hop(
            self, features: Any, current_node: str, destination: str, topology: Topology
        ) -> str:
            # Predicts next hop C which is not connected to A
            return "C"

    disconnected_router = DisconnectedNNRouter()
    with pytest.raises(RoutingError, match="invalid next-hop"):
        disconnected_router.compute_path(topo, "A", "C")


def test_cli_custom_router_integration(tmp_path: Any) -> None:
    """Test CLI invoking an ad-hoc custom router from external file."""
    runner = CliRunner()

    # Create temporary router file
    router_file = tmp_path / "my_cli_router.py"
    router_file.write_text(
        """
from nroute.routing.base import BaseRouter
class MyCliRouter(BaseRouter):
    def compute_path(self, topology, source, destination, weight=None):
        return [source, "cli-dynamic-hop", destination]
"""
    )

    # Create temporary topology file
    topo_file = tmp_path / "topo.json"
    topo_file.write_text(
        """{
        "nodes": [
            {"id": "A", "type": "router", "status": "up"},
            {"id": "B", "type": "router", "status": "up"}
        ],
        "edges": [
            {"source": "A", "target": "B", "status": "up"}
        ]
    }"""
    )

    res = runner.invoke(
        cli,
        [
            "route",
            "compute",
            "--allow-unsafe",
            "-t",
            str(topo_file),
            "-s",
            "A",
            "-d",
            "B",
            "-a",
            "custom",
            "--custom-router",
            f"{router_file}:MyCliRouter",
        ],
    )
    assert res.exit_code == 0
    assert "cli-dynamic-hop" in res.output
    assert "CUSTOM" in res.output
