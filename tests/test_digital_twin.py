"""Phase 1 integration tests for the Digital Twin Engine.

Tests the full stack bottom-up:
  1. OpenConfig schemas
  2. Config parser
  3. Analytical Engine
  4. Change-Impact Simulator
  5. RCA Correlator
  6. Audit Trail
  7. Digital Twin Engine orchestrator
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from nroute.audit import AuditAction, AuditTrail
from nroute.core.openconfig import (
    BGPConfig,
    BGPNeighborConfig,
    ConfigChange,
    DeviceConfig,
    InterfaceConfig,
    InterfaceState,
    OSPFConfig,
    OSPFInterfaceConfig,
)
from nroute.core.topology import Topology
from nroute.ingestion.config_parser import ConfigParser
from nroute.simulation.change_impact import (
    AnalyticalEngine,
    ChangeImpactSimulator,
)
from nroute.simulation.digital_twin import DigitalTwinEngine
from nroute.simulation.rca import (
    EventCategory,
    EventSeverity,
    NetworkEvent,
    RCACorrelator,
    classify_event,
    load_events,
)

# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def sample_topology() -> Topology:
    """Create a simple diamond topology: R1→R2→R4, R1→R3→R4."""
    topo = Topology()
    for node in ["R1", "R2", "R3", "R4"]:
        topo.add_node(node, type="router")
    topo.add_edge("R1", "R2", latency=5.0, bandwidth=1000.0, interface="Gi0/1")
    topo.add_edge("R1", "R3", latency=10.0, bandwidth=500.0, interface="Gi0/2")
    topo.add_edge("R2", "R4", latency=5.0, bandwidth=1000.0, interface="Gi0/1")
    topo.add_edge("R3", "R4", latency=3.0, bandwidth=500.0, interface="Gi0/1")
    return topo


@pytest.fixture
def tmp_dir() -> Path:
    """Create a temporary directory for test files."""
    d = Path(tempfile.mkdtemp())
    return d


# ── 1. OpenConfig Schema Tests ───────────────────────────────


class TestOpenConfigSchemas:
    """Verify Pydantic schema construction and validation."""

    def test_device_config_minimal(self) -> None:
        dev = DeviceConfig(hostname="R1")
        assert dev.hostname == "R1"
        assert dev.vendor == "generic"
        assert dev.interfaces == []

    def test_device_config_full(self) -> None:
        dev = DeviceConfig(
            hostname="R1",
            vendor="cisco",
            interfaces=[
                InterfaceConfig(
                    name="Gi0/1",
                    bandwidth=10000.0,
                    ipv4_address="10.0.0.1/30",
                ),
            ],
            ospf=OSPFConfig(
                router_id="1.1.1.1",
                interfaces=[
                    OSPFInterfaceConfig(
                        interface_name="Gi0/1",
                        cost=10,
                        area="0.0.0.0",
                    ),
                ],
            ),
            bgp=BGPConfig(
                local_as=65001,
                neighbors=[
                    BGPNeighborConfig(
                        neighbor_address="10.0.0.2",
                        remote_as=65002,
                    ),
                ],
            ),
            metadata={"role": "core", "location": "DC1"},
        )
        assert dev.vendor == "cisco"
        assert len(dev.interfaces) == 1
        assert dev.ospf is not None
        assert dev.ospf.interfaces[0].cost == 10
        assert dev.bgp is not None
        assert dev.bgp.local_as == 65001

    def test_config_change_schema(self) -> None:
        change = ConfigChange(
            description="Shut down R1→R2 link",
            link_changes=[{"src": "R1", "dst": "R2", "status": "down"}],
        )
        assert len(change.link_changes) == 1
        assert change.description == "Shut down R1→R2 link"

    def test_interface_state_enum(self) -> None:
        iface = InterfaceConfig(name="Gi0/1", state=InterfaceState.DOWN)
        assert iface.state == InterfaceState.DOWN
        assert iface.state.value == "down"


# ── 2. Config Parser Tests ───────────────────────────────────


class TestConfigParser:
    """Verify config loading and topology application."""

    def test_load_yaml_config(self, tmp_dir: Path) -> None:
        config_data = {
            "hostname": "R1",
            "vendor": "cisco",
            "interfaces": [
                {"name": "Gi0/1", "bandwidth": 10000.0},
            ],
        }
        config_file = tmp_dir / "device.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        configs = ConfigParser.load_device_configs(config_file)
        assert len(configs) == 1
        assert configs[0].hostname == "R1"

    def test_load_json_config(self, tmp_dir: Path) -> None:
        config_data = {
            "devices": [
                {"hostname": "R1"},
                {"hostname": "R2"},
            ]
        }
        config_file = tmp_dir / "devices.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f)

        configs = ConfigParser.load_device_configs(config_file)
        assert len(configs) == 2

    def test_apply_creates_nodes(self, sample_topology: Topology) -> None:
        configs = [DeviceConfig(hostname="R5", metadata={"role": "gateway"})]
        ConfigParser.apply_device_configs(sample_topology, configs)
        assert "R5" in sample_topology.nodes

    def test_apply_change_creates_copy(self, sample_topology: Topology) -> None:
        change = ConfigChange(
            link_changes=[{"src": "R1", "dst": "R2", "status": "down"}]
        )
        modified = ConfigParser.apply_change(sample_topology, change)
        # Original unchanged
        assert sample_topology.get_edge("R1", "R2")["status"] == "up"
        # Copy modified
        assert modified.get_edge("R1", "R2")["status"] == "down"

    def test_load_change_file(self, tmp_dir: Path) -> None:
        change_data = {
            "description": "Test change",
            "node_changes": [{"id": "R1", "status": "down"}],
        }
        change_file = tmp_dir / "change.yaml"
        import yaml

        with open(change_file, "w") as f:
            yaml.dump(change_data, f)

        change = ConfigParser.load_change(change_file)
        assert change.description == "Test change"
        assert len(change.node_changes) == 1


# ── 3. Analytical Engine Tests ───────────────────────────────


class TestAnalyticalEngine:
    """Verify static graph analysis."""

    def test_active_graph_excludes_down(self, sample_topology: Topology) -> None:
        sample_topology.set_link_down("R1", "R2")
        g = AnalyticalEngine.get_active_graph(sample_topology)
        assert not g.has_edge("R1", "R2")
        assert g.has_edge("R1", "R3")

    def test_shortest_paths(self, sample_topology: Topology) -> None:
        g = AnalyticalEngine.get_active_graph(sample_topology)
        paths = AnalyticalEngine.compute_all_pairs_shortest_paths(g)
        assert "R4" in paths.get("R1", {})
        # R1→R2→R4 has latency 10, R1→R3→R4 has latency 13
        path = paths["R1"]["R4"]
        assert path == ["R1", "R2", "R4"]

    def test_reachability(self, sample_topology: Topology) -> None:
        g = AnalyticalEngine.get_active_graph(sample_topology)
        reach = AnalyticalEngine.compute_reachability(g)
        assert "R4" in reach["R1"]

    def test_path_latency(self, sample_topology: Topology) -> None:
        g = AnalyticalEngine.get_active_graph(sample_topology)
        lat = AnalyticalEngine.compute_path_latency(g, ["R1", "R2", "R4"])
        assert lat == 10.0  # 5 + 5

    def test_reachability_after_failure(self, sample_topology: Topology) -> None:
        sample_topology.set_link_down("R1", "R2")
        sample_topology.set_link_down("R1", "R3")
        g = AnalyticalEngine.get_active_graph(sample_topology)
        reach = AnalyticalEngine.compute_reachability(g)
        # R1 can reach nothing
        assert "R4" not in reach.get("R1", set())


# ── 4. Change-Impact Simulator Tests ────────────────────────


class TestChangeImpactSimulator:
    """Verify blast-radius computation."""

    def test_no_impact_change(self, sample_topology: Topology) -> None:
        change = ConfigChange(description="No-op change")
        sim = ChangeImpactSimulator(sample_topology)
        result = sim.simulate(change)
        assert result.newly_unreachable_pairs == 0
        assert result.path_changed_pairs == 0

    def test_link_down_creates_impact(self, sample_topology: Topology) -> None:
        change = ConfigChange(
            description="Shut R1→R2",
            link_changes=[{"src": "R1", "dst": "R2", "status": "down"}],
        )
        sim = ChangeImpactSimulator(sample_topology)
        result = sim.simulate(change)
        # Path R1→R4 should change from R1→R2→R4 to R1→R3→R4
        assert result.path_changed_pairs > 0

    def test_node_down_creates_unreachable(self, sample_topology: Topology) -> None:
        # Take down R2 AND R3 — R4 becomes unreachable from R1
        change = ConfigChange(
            description="Take down R2 and R3",
            node_changes=[
                {"id": "R2", "status": "down"},
                {"id": "R3", "status": "down"},
            ],
        )
        sim = ChangeImpactSimulator(sample_topology)
        result = sim.simulate(change)
        assert result.newly_unreachable_pairs > 0

    def test_to_dict_serializable(self, sample_topology: Topology) -> None:
        change = ConfigChange(
            link_changes=[{"src": "R1", "dst": "R2", "status": "down"}]
        )
        sim = ChangeImpactSimulator(sample_topology)
        result = sim.simulate(change)
        d = result.to_dict()
        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert isinstance(json_str, str)


# ── 5. RCA Correlator Tests ──────────────────────────────────


class TestRCACorrelator:
    """Verify root-cause analysis."""

    def test_classify_bgp_event(self) -> None:
        evt = NetworkEvent(event_type="bgp_session_down", node_id="R1")
        classified = classify_event(evt)
        assert classified.category == EventCategory.ROUTING
        assert classified.severity == EventSeverity.CRITICAL

    def test_classify_interface_event(self) -> None:
        evt = NetworkEvent(event_type="link_down", node_id="R2")
        classified = classify_event(evt)
        assert classified.category == EventCategory.INTERFACE

    def test_rca_identifies_root_cause(self, sample_topology: Topology) -> None:
        events = [
            NetworkEvent(
                event_id="evt_1",
                timestamp=100.0,
                node_id="R1",
                peer_node="R2",
                event_type="link_down",
            ),
            NetworkEvent(
                event_id="evt_2",
                timestamp=100.5,
                node_id="R2",
                event_type="ospf_adjacency_loss",
                peer_node="R1",
            ),
            NetworkEvent(
                event_id="evt_3",
                timestamp=101.0,
                node_id="R2",
                event_type="ospf_spf",
            ),
        ]
        events = [classify_event(e) for e in events]

        correlator = RCACorrelator(sample_topology)
        result = correlator.diagnose(events)

        assert result.root_cause is not None
        # Root cause should be the routing event (higher priority)
        assert result.root_cause.category == EventCategory.ROUTING
        assert result.total_events == 3
        assert len(result.correlation_chain) >= 1

    def test_rca_empty_events(self, sample_topology: Topology) -> None:
        correlator = RCACorrelator(sample_topology)
        result = correlator.diagnose([])
        assert result.root_cause is None

    def test_load_events_from_file(self, tmp_dir: Path) -> None:
        events_data = [
            {
                "event_id": "e1",
                "timestamp": 1.0,
                "node_id": "R1",
                "event_type": "link_down",
            },
            {
                "event_id": "e2",
                "timestamp": 2.0,
                "node_id": "R2",
                "event_type": "bgp_session_down",
            },
        ]
        events_file = tmp_dir / "events.json"
        with open(events_file, "w") as f:
            json.dump(events_data, f)

        events = load_events(events_file)
        assert len(events) == 2


# ── 6. Audit Trail Tests ────────────────────────────────────


class TestAuditTrail:
    """Verify audit logging and querying."""

    def test_record_and_query(self) -> None:
        trail = AuditTrail()
        trail.record(
            AuditAction.CONFIG_CHANGE,
            actor="alice",
            source="R1",
            explanation="Test change",
        )
        trail.record(
            AuditAction.RCA_DIAGNOSIS,
            actor="system",
        )

        assert len(trail.records) == 2
        config_recs = trail.query(action=AuditAction.CONFIG_CHANGE)
        assert len(config_recs) == 1
        assert config_recs[0].actor == "alice"

    def test_file_backed_trail(self, tmp_dir: Path) -> None:
        log_path = tmp_dir / "audit.ndjson"
        trail = AuditTrail(log_file=log_path)
        trail.record(AuditAction.TOPOLOGY_MUTATION, explanation="Test")

        assert log_path.exists()
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["action"] == "topology_mutation"

    def test_export_json(self, tmp_dir: Path) -> None:
        trail = AuditTrail()
        trail.record(AuditAction.LINK_FAILURE, source="R1", target="R2")
        export_path = tmp_dir / "export.json"
        trail.export_json(export_path)

        with open(export_path) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_summary(self) -> None:
        trail = AuditTrail()
        trail.record(AuditAction.CONFIG_CHANGE)
        trail.record(AuditAction.CONFIG_CHANGE)
        trail.record(AuditAction.RCA_DIAGNOSIS)

        summary = trail.summary()
        assert summary["total_records"] == 3
        assert summary["action_counts"]["config_change"] == 2


# ── 7. Digital Twin Engine Integration ──────────────────────


class TestDigitalTwinEngine:
    """End-to-end integration tests."""

    def test_full_lifecycle(self, sample_topology: Topology, tmp_dir: Path) -> None:
        # Save topology to file
        topo_path = tmp_dir / "topology.json"
        sample_topology.save(topo_path)

        # Instantiate engine
        twin = DigitalTwinEngine(audit_log=tmp_dir / "audit.ndjson")

        # Load
        twin.load_topology(topo_path)
        assert twin.topology.node_count == 4

        # Health check
        health = twin.health_summary()
        assert health["total_nodes"] == 4
        assert health["active_nodes"] == 4

        # Reachability
        reach = twin.compute_reachability()
        assert "R4" in reach["R1"]

        # Change-impact
        change = ConfigChange(
            description="Shut R1→R2",
            link_changes=[{"src": "R1", "dst": "R2", "status": "down"}],
        )
        result = twin.simulate_change(change)
        assert result.path_changed_pairs > 0

        # Audit trail
        assert len(twin.audit.records) >= 2

    def test_diagnose_from_file(self, sample_topology: Topology, tmp_dir: Path) -> None:
        topo_path = tmp_dir / "topology.json"
        sample_topology.save(topo_path)

        events_data = [
            {
                "event_id": "e1",
                "timestamp": 1.0,
                "node_id": "R1",
                "event_type": "link_down",
                "peer_node": "R2",
            },
        ]
        events_file = tmp_dir / "events.json"
        with open(events_file, "w") as f:
            json.dump(events_data, f)

        twin = DigitalTwinEngine()
        twin.load_topology(topo_path)
        result = twin.diagnose(events_file)
        assert result.root_cause is not None

    def test_topology_not_loaded_raises(self) -> None:
        twin = DigitalTwinEngine()
        with pytest.raises(RuntimeError, match="No topology loaded"):
            _ = twin.topology

    def test_set_topology_and_snapshots(self, sample_topology: Topology) -> None:
        twin = DigitalTwinEngine()
        twin.set_topology(sample_topology)
        assert twin.topology == sample_topology
        snaps = twin.snapshots
        assert len(snaps) == 1
        assert snaps[0].metadata["label"] == "programmatic_set"
        snap_dict = snaps[0].to_dict()
        assert snap_dict["node_count"] == 4
        assert snap_dict["edge_count"] == 4

    def test_simulate_change_from_file_and_no_impact_counterfactual(
        self, sample_topology: Topology, tmp_dir: Path
    ) -> None:
        topo_path = tmp_dir / "topology.json"
        sample_topology.save(topo_path)

        twin = DigitalTwinEngine()
        twin.load_topology(topo_path)

        # 1. No impact change (no-op)
        noop_change = ConfigChange(description="noop")
        res_noop = twin.simulate_change(noop_change)
        assert res_noop.newly_unreachable_pairs == 0
        assert res_noop.path_changed_pairs == 0

        # 2. Change from file
        change_data = {
            "description": "Shut R1-R2 from file",
            "link_changes": [{"src": "R1", "dst": "R2", "status": "down"}],
        }
        change_file = tmp_dir / "change.json"
        with open(change_file, "w") as f:
            json.dump(change_data, f)

        res_file = twin.simulate_change(change_file)
        assert res_file.path_changed_pairs > 0

    def test_compute_shortest_paths(self, sample_topology: Topology) -> None:
        twin = DigitalTwinEngine()
        twin.set_topology(sample_topology)
        paths = twin.compute_shortest_paths()
        assert "R4" in paths.get("R1", {})

    def test_ingest_config(self, sample_topology: Topology, tmp_dir: Path) -> None:
        import yaml

        config_data = {
            "hostname": "R1",
            "vendor": "cisco",
            "interfaces": [
                {"name": "Gi0/1", "bandwidth": 2000.0},
            ],
        }
        config_file = tmp_dir / "device.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        twin = DigitalTwinEngine()
        twin.set_topology(sample_topology)
        hostnames = twin.ingest_config(config_file)
        assert hostnames == ["R1"]
        edge = twin.topology.get_edge("R1", "R2")
        assert edge["bandwidth"] == 2000.0
