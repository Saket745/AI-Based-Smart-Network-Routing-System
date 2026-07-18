"""Unit tests for nroute extensibility registries and custom model support."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from nroute import BaseRouter, get_router, register_router
from nroute.core.topology import Topology
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor

# ── Test Router Registry ──────────────────────────────────────────────────────


@register_router("mock-custom-router")
class MockCustomRouter(BaseRouter):
    """Mock router for registry validation."""

    def __init__(self, topology: Topology | None = None) -> None:
        self.topology = topology

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: Any = None,
    ) -> list[str]:
        return [source, destination]


def test_router_registration() -> None:
    """Verify custom routers can be registered and retrieved by get_router."""
    router = get_router("mock-custom-router")
    assert isinstance(router, MockCustomRouter)
    assert router.topology is None

    # Test initialization with topology context
    topo = Topology()
    router_with_topo = get_router("mock-custom-router", topology=topo)
    assert isinstance(router_with_topo, MockCustomRouter)
    assert router_with_topo.topology is topo


# ── Test Custom ML Predictor Support ──────────────────────────────────────────


class DummyScikitPredictor:
    """Mock scikit-learn model with fit and predict_proba."""

    def __init__(self) -> None:
        self.fitted = False

    def fit(self, x: Any, y: Any) -> None:
        self.fitted = True

    def predict_proba(self, x: Any) -> np.ndarray:
        # Return probability matrix
        return np.array([[0.1, 0.9] for _ in range(len(x))])


def test_custom_congestion_predictor() -> None:
    """Verify custom classifier models can be wrapped by CongestionPredictor."""
    dummy = DummyScikitPredictor()
    predictor = CongestionPredictor(model_type="custom", custom_model=dummy)

    assert predictor.model_type == "custom"
    assert predictor.model is dummy
    assert not predictor.is_trained

    # Train
    features = pd.DataFrame({"utilization_t": [0.5, 0.8], "bandwidth": [1000, 1000]})
    labels = np.array([0, 1])
    metrics = predictor.train(features, labels)

    assert dummy.fitted
    assert predictor.is_trained
    assert "accuracy" in metrics

    # Predict
    preds = predictor.predict(features)
    assert len(preds) == 2
    assert "congested" in preds
    assert "probability" in preds
    assert preds["congested"].iloc[0]  # 0.9 probability


# ── Test Custom Anomaly Detector Support ──────────────────────────────────────


class DummyAnomalyModel:
    """Mock anomaly model with fit and decision_function."""

    def __init__(self) -> None:
        self.fitted = False

    def fit(self, x: Any) -> None:
        self.fitted = True

    def decision_function(self, x: Any) -> np.ndarray:
        # returns anomaly scores
        return np.array([0.1, -0.4])  # 0.1 (normal), -0.4 (anomalous)

    def predict(self, x: Any) -> np.ndarray:
        return np.array([1, -1])  # 1 (normal), -1 (anomaly)


def test_custom_anomaly_detector() -> None:
    """Verify custom anomaly models can be wrapped by AnomalyDetector."""
    dummy = DummyAnomalyModel()
    detector = AnomalyDetector(model_type="custom", custom_model=dummy)

    assert detector.model_type == "custom"
    assert detector.model is dummy
    assert not detector.is_trained

    # Fit
    features = pd.DataFrame(
        {
            "bytes_per_second": [100.0, 100000000.0],
            "src_ip_entropy": [3.0, 0.5],
            "flow_count": [5, 100],
        }
    )
    detector.fit(features)

    assert dummy.fitted
    assert detector.is_trained

    # Detect
    results = detector.detect(features)
    assert len(results) == 2
    assert "anomaly_score" in results
    assert "is_anomaly" in results
    assert "anomaly_type" in results

    assert not results["is_anomaly"].iloc[0]
    assert results["is_anomaly"].iloc[1]


def test_get_router_all_types() -> None:
    """Verify that get_router resolves all built-in standard algorithms and handles invalid input correctly."""
    import pytest

    from nroute.routing.ai import AIRouter
    from nroute.routing.bellman_ford import BellmanFordRouter
    from nroute.routing.bfs import BFSRouter
    from nroute.routing.dijkstra import DijkstraRouter
    from nroute.routing.ecmp import ECMPRouter
    from nroute.routing.negotiation import NegotiationRouter
    from nroute.routing.rl_router import RLRouter

    topo = Topology()

    assert isinstance(get_router("dijkstra"), DijkstraRouter)
    assert isinstance(get_router("bellman-ford"), BellmanFordRouter)
    assert isinstance(get_router("bellmanford"), BellmanFordRouter)
    assert isinstance(get_router("ecmp"), ECMPRouter)
    assert isinstance(get_router("ai", topology=topo), AIRouter)
    assert isinstance(get_router("bfs"), BFSRouter)

    # RL/PPO/DQN
    rl_router = get_router("rl", topology=topo)
    assert isinstance(rl_router, RLRouter)
    assert rl_router.algorithm == "ppo"

    ppo_router = get_router("ppo", topology=topo)
    assert isinstance(ppo_router, RLRouter)
    assert ppo_router.algorithm == "ppo"

    dqn_router = get_router("dqn", topology=topo)
    assert isinstance(dqn_router, RLRouter)
    assert dqn_router.algorithm == "dqn"

    # Negotiation variations
    neg_router = get_router("negotiation")
    assert isinstance(neg_router, NegotiationRouter)
    assert neg_router.profile == "balanced"

    neg_latency = get_router("negotiation-latency")
    assert isinstance(neg_latency, NegotiationRouter)
    assert neg_latency.profile == "latency"

    neg_congestion = get_router("negotiation-congestion")
    assert isinstance(neg_congestion, NegotiationRouter)
    assert neg_congestion.profile == "congestion"

    neg_balanced = get_router("negotiation-balanced")
    assert isinstance(neg_balanced, NegotiationRouter)
    assert neg_balanced.profile == "balanced"

    # Invalid
    with pytest.raises(ValueError, match="Unknown router name 'nonexistent'"):
        get_router("nonexistent")
