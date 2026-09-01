"""Unit tests for benchmark pilot infrastructure and instrumentation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from nroute.benchmark.dynamic_dijkstra import DynamicDijkstraRouter
from nroute.benchmark.instrumentation import InstrumentedRouter, PilotMetricsRecorder
from nroute.core.generators import TopologyGenerator
from nroute.core.traffic import FlowRecord
from nroute.routing.base import BaseRouter
from nroute.routing.dijkstra import DijkstraRouter


class MockAIRouterWithFallback(BaseRouter):
    """Mock router that triggers fallback under specific conditions."""

    def __init__(self) -> None:
        super().__init__()
        self.should_fallback = False

    def _cascade_fallback(
        self, topology: Any, source: str, destination: str, **kwargs: Any
    ) -> list[str]:
        return DijkstraRouter().compute_path(topology, source, destination)

    def compute_path(
        self, topology: Any, source: str, destination: str, **kwargs: Any
    ) -> list[str]:
        if self.should_fallback:
            return self._cascade_fallback(
                topology, source, destination, reason="mock_low_confidence"
            )
        return [source, destination]


def test_dynamic_dijkstra_router() -> None:
    """Verify DynamicDijkstraRouter applies dynamic utilization penalties correctly."""
    topo = TopologyGenerator.random(n_nodes=4, edge_prob=1.0, seed=42)
    # Give edge ("0", "1") high utilization
    topo.update_edge("0", "1", latency=5.0, utilization=0.9)
    # Give alternative path ("0", "2", "1") low utilization
    topo.update_edge("0", "2", latency=5.0, utilization=0.0)
    topo.update_edge("2", "1", latency=5.0, utilization=0.0)

    static_router = DijkstraRouter()
    path_static = static_router.compute_path(topo, "0", "1")
    # Static Dijkstra takes the 1-hop path with 5ms latency
    assert path_static == ["0", "1"]

    dynamic_router = DynamicDijkstraRouter(alpha=5.0)
    path_dynamic = dynamic_router.compute_path(topo, "0", "1")
    # Dynamic Dijkstra penalizes 0->1 (5 * (1 + 5*0.9) = 27.5ms), routes around via "2" (10ms total)
    assert path_dynamic == ["0", "2", "1"]


def test_instrumented_router_provenance() -> None:
    """Verify InstrumentedRouter captures route provenance and fallback events explicitly."""
    # 1. Classical baseline router
    dijkstra = DijkstraRouter()
    inst_dijkstra = InstrumentedRouter(dijkstra)
    topo = TopologyGenerator.fat_tree(k=4, seed=42)
    path = inst_dijkstra.compute_path(topo, "pod_0_host_0_0", "pod_0_host_0_1")
    assert len(path) > 1
    assert inst_dijkstra.total_queries == 1
    assert inst_dijkstra.fallback_count == 0
    assert inst_dijkstra.fallback_ratio == 0.0
    assert inst_dijkstra.query_records[0].route_source == "classical_baseline"

    # 2. AI router native policy
    mock_ai = MockAIRouterWithFallback()
    inst_ai = InstrumentedRouter(mock_ai)
    inst_ai.compute_path(topo, "pod_0_host_0_0", "pod_0_host_0_1")
    assert inst_ai.fallback_count == 0
    assert inst_ai.query_records[0].route_source == "native_policy"

    # 3. AI router triggering fallback
    mock_ai.should_fallback = True
    inst_ai.compute_path(topo, "pod_0_host_0_0", "pod_0_host_0_1")
    assert inst_ai.fallback_count == 1
    assert inst_ai.fallback_ratio == 0.5
    assert inst_ai.query_records[1].route_source == "fallback"
    assert inst_ai.query_records[1].fallback_reason == "mock_low_confidence"


def test_pilot_metrics_recorder() -> None:
    """Verify PilotMetricsRecorder computes high-precision percentiles, Jain index, and stretch."""
    topo = TopologyGenerator.fat_tree(k=4, seed=42)
    recorder = PilotMetricsRecorder(base_topology=topo, failure_tick=10, recovery_tick=20)

    # Mock engine
    mock_engine = MagicMock()
    mock_engine.topology = topo

    # Simulate tick 0
    mock_flow1 = FlowRecord(
        source="pod_0_host_0_0",
        destination="pod_0_host_0_1",
        bytes=1000,
        packets=5,
        duration=0.010,  # 10ms
        protocol="TCP",
        timestamp=0.0,
    )
    mock_engine.last_tick_completed_flows = [mock_flow1]
    mock_engine.active_flows = [
        {"flow": mock_flow1, "path": ["pod_0_host_0_0", "pod_0_edge_0", "pod_0_host_0_1"]}
    ]
    mock_metric = MagicMock()
    mock_metric.throughput = 100.0
    mock_metric.packet_loss_rate = 0.0
    mock_engine.collector.results = [mock_metric]

    recorder.on_tick(0, mock_engine)

    # Simulate tick 1 with another flow
    mock_flow2 = FlowRecord(
        source="pod_0_host_0_0",
        destination="pod_0_host_0_1",
        bytes=2000,
        packets=10,
        duration=0.020,  # 20ms
        protocol="TCP",
        timestamp=1.0,
    )
    mock_engine.last_tick_completed_flows = [mock_flow2]
    recorder.on_tick(1, mock_engine)

    inst_router = InstrumentedRouter(DijkstraRouter())
    inst_router.compute_path(topo, "pod_0_host_0_0", "pod_0_host_0_1")

    summary = recorder.compute_summary(inst_router)

    assert summary["total_completed_flows"] == 2
    assert summary["p50_latency_ms"] == 15.0  # Median between 10ms and 20ms
    assert summary["p95_latency_ms"] == 19.5
    assert summary["mean_latency_ms"] == 15.0
    assert summary["mean_jain_fairness"] <= 1.0
    assert summary["mean_path_stretch"] >= 1.0
    assert summary["total_queries"] == 1
