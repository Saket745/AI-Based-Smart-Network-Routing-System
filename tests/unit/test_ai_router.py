"""Unit tests for the AI-powered congestion-avoidance router."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from nroute.core.topology import Topology
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
    assert predictions.loc["B->D", "congested"] == True
    assert predictions.loc["A->B", "congested"] == False

    # Compute path A -> D.
    # Original shortest path: A -> B -> D (latency = 10 + 5 = 15)
    # But link B->D has predicted congestion prob ~1.0.
    # Dynamic weight of B->D = 5.0 * (1 + 10.0 * 1.0) = 55.0
    # Dynamic weight of other links (e.g. B->E, E->D) = latency * 1.0
    # Path A -> B -> E -> D has total dynamic weight = 10 + 8 + 3 = 21
    # Thus, AIRouter should choose A -> B -> E -> D to avoid the congested link B->D!
    path = router.compute_path(topo, "A", "D")
    assert path == ["A", "B", "E", "D"]
