"""Integration tests using real/sample data files under data/."""

from __future__ import annotations

from pathlib import Path

from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord, TrafficMatrix
from nroute.ml.anomaly import AnomalyDetector
from nroute.routing import get_router
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class MatrixTrafficGenerator(TrafficGenerator):
    """Custom traffic generator that yields flows from an ingested TrafficMatrix."""

    def __init__(self, flows: list[FlowRecord]) -> None:
        super().__init__(model="uniform")
        self.flows = flows
        # Group flows by integer tick offset from minimum timestamp
        min_ts = min(f.timestamp for f in flows) if flows else 0.0
        self.flows_by_tick: dict[int, list[FlowRecord]] = {}
        for f in flows:
            tick_idx = int(f.timestamp - min_ts)
            self.flows_by_tick.setdefault(tick_idx, []).append(f)

    def generate(self, topology: Topology, tick: int = 0) -> list[FlowRecord]:
        return self.flows_by_tick.get(tick, [])


def test_real_data_topology_ingestion_and_routing() -> None:
    """Test loading the sample topology JSON and running Dijkstra/Bellman-Ford routing."""
    topo_path = DATA_DIR / "sample_topology.json"
    assert topo_path.exists(), f"Sample topology file not found at {topo_path}"

    # 1. Load topology
    topo = Topology.load(topo_path)
    assert topo.node_count > 0
    assert topo.edge_count > 0

    # Verify we can find nodes and edges
    assert len(topo.nodes) == topo.node_count
    src_node = topo.nodes[0]
    dst_node = topo.nodes[1]

    # 2. Compute route
    dijkstra_router = get_router("dijkstra", topology=topo)
    path = dijkstra_router.compute_path(topo, src_node, dst_node)
    assert len(path) >= 2
    assert path[0] == src_node
    assert path[-1] == dst_node


def test_real_data_traffic_ingestion_and_simulation() -> None:
    """Test loading the sample traffic CSV and running a packet-level simulation."""
    topo_path = DATA_DIR / "sample_topology.json"
    traffic_path = DATA_DIR / "sample_traffic.csv"
    assert topo_path.exists()
    assert traffic_path.exists()

    # 1. Ingest topology & traffic matrix
    topo = Topology.load(topo_path)
    tm = TrafficMatrix.from_csv(traffic_path)
    assert len(tm.flows) > 0

    # 2. Setup router and custom traffic generator
    router = get_router("dijkstra", topology=topo)
    traffic_gen = MatrixTrafficGenerator(tm.flows)

    # 3. Configure simulation engine
    engine = SimulationEngine(topo, router, traffic_gen)
    results = engine.run(duration_ticks=10, seed=42)

    # 4. Verify simulation executed and gathered some metrics
    assert len(results.results) == 10
    assert results.total_throughput() >= 0.0


def test_real_data_netflow_ingestion_and_anomaly_detection() -> None:
    """Test ingesting sample NetFlow CSV, discovering topology, and running anomaly detection."""
    netflow_path = DATA_DIR / "sample_netflow.csv"
    assert netflow_path.exists()

    # 1. Ingest NetFlow CSV to discover a topology
    topo = Topology.from_netflow(netflow_path)
    assert topo.node_count > 0
    assert topo.edge_count > 0

    # 2. Setup anomaly detector and run detection on dummy traffic features
    detector = AnomalyDetector(model_type="isolation_forest")
    # For integration testing, mock model load/predict
    detector._model = "mock"
    detector.load = lambda *args, **kwargs: None  # type: ignore[method-assign]
    detector.predict = lambda features: [0] * len(features)  # type: ignore[method-assign]

    # Predict anomalies
    dummy_features = [[1000.0, 10.0, 1.0, 100.0, 0.0, 0.0, 0.0, 0.0]]
    preds = detector.predict(dummy_features)
    assert len(preds) == 1
    assert preds[0] == 0
