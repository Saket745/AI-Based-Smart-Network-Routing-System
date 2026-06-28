"""Unit tests for the AI-powered congestion-avoidance router."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord, TrafficMatrix
from nroute.exceptions import RoutingError
from nroute.routing.ai import AIRouter


def _get_topo(small_graph_data: dict[str, Any]) -> Topology:
    """Helper to convert test fixture graph data schema to Topology.from_dict structure."""
    edges = []
    for edge in small_graph_data.get("edges", []):
        edges.append(
            {
                "source": edge.get("src"),
                "target": edge.get("dst"),
                "bandwidth": edge.get("bandwidth"),
                "latency": edge.get("latency"),
                "jitter": edge.get("jitter"),
                "packet_loss": edge.get("packet_loss"),
                "utilization": edge.get("utilization"),
                "status": edge.get("status"),
            }
        )
    data = {"nodes": small_graph_data.get("nodes", []), "edges": edges}
    return Topology.from_dict(data)


def test_ai_router_init() -> None:
    """Test AIRouter initialization."""
    router = AIRouter(
        congestion_model_type="lstm",
        anomaly_model_type="autoencoder",
        alpha=10.0,
        anomaly_alpha_scale=2.0,
    )
    assert router.alpha == 10.0
    assert router._base_alpha == 10.0
    assert router._anomaly_alpha_scale == 2.0
    assert router.congestion_predictor.model_type == "lstm"
    assert router.anomaly_detector.model_type == "autoencoder"
    assert not router.is_trained


def test_ai_router_fallback(small_graph_data: dict[str, Any]) -> None:
    """Test that untrained AIRouter falls back to Dijkstra shortest path."""
    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo)

    assert not router.is_trained

    # Path A -> D should be standard shortest path: A -> B -> D (15ms)
    path = router.compute_path(topo, "A", "D")
    assert path == ["A", "B", "D"]


def test_ai_router_congestion_avoidance(small_graph_data: dict[str, Any]) -> None:
    """Test that trained AIRouter dynamically avoids links predicted as congested."""
    from nroute.ml.feature_eng import extract_congestion_features

    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo, alpha=10.0)

    # We mock train the congestion predictor:
    # First set B->D utilization high in topology to extract matching features
    topo.update_edge("B", "D", utilization=0.95)

    # Extract features using the official helper
    df = extract_congestion_features(topo, [])
    labels = [1 if idx == "B->D" else 0 for idx in df.index]
    labels_arr = np.array(labels)

    # Train the predictor (duplicate dataset to satisfy XGBoost split constraints)
    train_df = pd.concat([df] * 10)
    train_labels = np.concatenate([labels_arr] * 10)
    router.train(features_congestion=train_df, labels_congestion=train_labels)
    assert router.congestion_predictor.is_trained
    assert router.is_trained

    # Let's verify that the predictor classifies B->D as congested
    predictions = router.congestion_predictor.predict(df)
    assert predictions.loc["B->D", "congested"]
    assert not predictions.loc["A->B", "congested"]

    # Compute path A -> D.
    # Original shortest path: A -> B -> D (latency = 10 + 5 = 15)
    # But link B->D has predicted congestion prob ~1.0.
    # Dynamic weight of B->D = 5.0 * (1 + 10.0 * 1.0) = 55.0
    # Dynamic weight of other links (e.g. B->E, E->D) = latency * 1.0
    # Path A -> B -> E -> D has total dynamic weight = 10 + 8 + 3 = 21
    # Thus, AIRouter should choose A -> B -> E -> D to avoid the congested link B->D!
    path = router.compute_path(topo, "A", "D")
    assert path == ["A", "B", "E", "D"]


def test_ai_router_anomaly_alpha_escalation(small_graph_data: dict[str, Any]) -> None:
    """Test that AIRouter escalates alpha when anomaly is detected and reverts when cleared."""
    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo, alpha=5.0, anomaly_alpha_scale=4.0)

    # Initially, alpha should be base value
    assert router.alpha == 5.0
    assert not router._anomaly_active

    # 1. Update with no trained detector
    tm = TrafficMatrix(
        flows=[
            FlowRecord(
                source="A",
                destination="D",
                bytes=1000,
                packets=10,
                duration=1.0,
                protocol="TCP",
                timestamp=0.0,
            )
        ]
    )
    router.update_traffic_history(tm)
    assert router.alpha == 5.0
    assert not router._anomaly_active

    # 2. Mock a trained detector that finds an anomaly
    router.anomaly_detector.is_trained = True
    with patch.object(router, "detect_anomalies") as mock_detect:
        # Mocking detect_anomalies to return a DataFrame with an anomaly (anomaly == -1)
        mock_detect.return_value = pd.DataFrame({"anomaly": [-1]}, index=["flow1"])

        router.update_traffic_history(tm)
        assert router._anomaly_active
        assert router.alpha == 20.0  # 5.0 * 4.0

        # 3. Anomaly cleared
        mock_detect.return_value = pd.DataFrame({"anomaly": [1]}, index=["flow1"])
        router.update_traffic_history(tm)
        assert not router._anomaly_active
        assert router.alpha == 5.0


def test_ai_router_train_all(small_graph_data: dict[str, Any]) -> None:
    """Test training both models via AIRouter.train."""
    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo)

    feat_cong = pd.DataFrame({"feat1": [1, 2]}, index=["A->B", "B->D"])
    labels_cong = np.array([0, 1])
    feat_anom = pd.DataFrame({"feat1": [1, 2, 3]})

    # Mock the underlying trainers to avoid actual ML training overhead
    with (
        patch.object(router.congestion_predictor, "train") as mock_train_cong,
        patch.object(router.anomaly_detector, "fit") as mock_fit_anom,
    ):
        mock_train_cong.return_value = {"accuracy": 0.9}

        results = router.train(
            features_congestion=feat_cong,
            labels_congestion=labels_cong,
            features_anomaly=feat_anom,
            epochs=5,
        )

        assert results["congestion"] == {"accuracy": 0.9}
        assert results["anomaly"] == {"status": "trained"}
        mock_train_cong.assert_called_once()
        mock_fit_anom.assert_called_once()


def test_ai_router_save_load(tmp_path: Any) -> None:
    """Test AIRouter save and load logic."""
    router = AIRouter()
    save_path = str(tmp_path / "ai_model")

    with (
        patch.object(router.congestion_predictor, "save") as mock_save_cong,
        patch.object(router.anomaly_detector, "save") as mock_save_anom,
    ):
        router.save(save_path)
        mock_save_cong.assert_called_with(f"{save_path}.congestion")
        mock_save_anom.assert_called_with(f"{save_path}.anomaly")

    with (
        patch.object(router.congestion_predictor, "load") as mock_load_cong,
        patch.object(router.anomaly_detector, "load") as mock_load_anom,
    ):
        # Mock load state
        def side_effect_cong(*args: Any, **kwargs: Any) -> None:
            router.congestion_predictor.is_trained = True

        mock_load_cong.side_effect = side_effect_cong

        router.load(save_path)
        mock_load_cong.assert_called_with(f"{save_path}.congestion")
        mock_load_anom.assert_called_with(f"{save_path}.anomaly")
        assert router.is_trained


def test_ai_router_error_cases(small_graph_data: dict[str, Any]) -> None:
    """Test AIRouter handling of missing nodes and prediction errors."""
    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo)

    # 1. Invalid source/dest
    with pytest.raises(RoutingError, match="Source node 'X' is down or does not exist"):
        router.compute_path(topo, "X", "D")

    with pytest.raises(RoutingError, match="Destination node 'Y' is down or does not exist"):
        router.compute_path(topo, "A", "Y")

    # 2. Prediction failure should still fallback
    router.congestion_predictor.is_trained = True
    with patch(
        "nroute.routing.ai.extract_congestion_features", side_effect=Exception("Feature error")
    ):
        path = router.compute_path(topo, "A", "D")
        assert path == ["A", "B", "D"]  # Dijkstra fallback


def test_ai_router_no_path_found(small_graph_data: dict[str, Any]) -> None:
    """Test that AIRouter falls back if no path is found with dynamic weights."""
    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo)
    router.congestion_predictor.is_trained = True

    # Use a side effect that only raises on the first call (AI weights)
    # but succeeds on subsequent calls (Dijkstra/BFS fallbacks)
    orig_shortest_path = nx.shortest_path

    def side_effect(*args, **kwargs):
        if "weight" in kwargs and kwargs["weight"] is not None:
            raise nx.NetworkXNoPath
        return orig_shortest_path(*args, **kwargs)

    with patch("networkx.shortest_path", side_effect=side_effect):
        # Should fallback to cascade
        path = router.compute_path(topo, "A", "D")
        assert path == ["A", "B", "D"]


def test_ai_router_predict_methods(small_graph_data: dict[str, Any]) -> None:
    """Test explicit predict_congestion and detect_anomalies methods."""
    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo)

    tm = TrafficMatrix(flows=[])

    with (
        patch("nroute.routing.ai.extract_congestion_features") as mock_feat_cong,
        patch.object(router.congestion_predictor, "predict") as mock_pred_cong,
    ):
        router.predict_congestion(topo, [])
        mock_feat_cong.assert_called_once()
        mock_pred_cong.assert_called_once()

    with (
        patch("nroute.routing.ai.extract_anomaly_features") as mock_feat_anom,
        patch.object(router.anomaly_detector, "detect") as mock_det_anom,
    ):
        router.detect_anomalies(tm)
        mock_feat_anom.assert_called_once()
        mock_det_anom.assert_called_once()


def test_ai_router_traffic_history_limit(small_graph_data: dict[str, Any]) -> None:
    """Test that traffic history length is limited."""
    router = AIRouter()
    tm = TrafficMatrix(flows=[])

    # Add 60 snapshots with max_history=50
    for _ in range(60):
        router.update_traffic_history(tm, max_history=50)

    assert len(router.traffic_history) == 50


def test_ai_router_node_down(small_graph_data: dict[str, Any]) -> None:
    """Test AIRouter behavior when source or destination node is down."""
    topo = _get_topo(small_graph_data)
    router = AIRouter(topology=topo)

    # Mark node B as down
    topo.set_node_down("B")

    # Source down
    with pytest.raises(RoutingError, match="Source node 'B' is down"):
        router.compute_path(topo, "B", "D")

    # Destination down
    with pytest.raises(RoutingError, match="Destination node 'B' is down"):
        router.compute_path(topo, "A", "B")


def test_ai_router_anomaly_detection_exception(small_graph_data: dict[str, Any]) -> None:
    """Test that AIRouter handles exceptions during anomaly detection gracefully."""
    router = AIRouter()
    router.anomaly_detector.is_trained = True
    tm = TrafficMatrix(flows=[])

    with patch.object(router, "detect_anomalies", side_effect=Exception("Detection failed")):
        # Should not raise exception, should just set has_anomaly=False
        router.update_traffic_history(tm)
        assert not router._anomaly_active
        assert router.alpha == router._base_alpha
