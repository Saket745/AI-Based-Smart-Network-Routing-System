"""Digital Twin Engine — Phase 1 orchestrator.

Wires together:
  * Config parsing & topology translation
  * Analytical Path Engine (Mode A)
  * Change-Impact Simulator
  * Root-Cause Analysis correlator
  * Three-tier Audit Trail

Provides a single-entry-point API for both the CLI and the FastAPI server.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nroute.audit import AuditAction, AuditTrail
from nroute.core.openconfig import ConfigChange
from nroute.core.topology import Topology
from nroute.ingestion.config_parser import ConfigParser
from nroute.simulation.change_impact import (
    AnalyticalEngine,
    BlastRadius,
    ChangeImpactSimulator,
)
from nroute.simulation.rca import (
    NetworkEvent,
    RCACorrelator,
    RCAResult,
    load_events,
)
from nroute.utils.logging import get_logger

logger = get_logger(__name__)


# ── Snapshot data class ──────────────────────────────────────


@dataclass
class TopologySnapshot:
    """Point-in-time topology state for comparison."""

    timestamp: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    active_nodes: int = 0
    active_edges: int = 0
    reachability_matrix: dict[str, set[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "active_nodes": self.active_nodes,
            "active_edges": self.active_edges,
            "reachability_pairs": sum(
                len(v) for v in self.reachability_matrix.values()
            ),
            "metadata": self.metadata,
        }


# ── Digital Twin Engine ──────────────────────────────────────


class DigitalTwinEngine:
    """Stateful Digital Twin of the network.

    Manages:
    * A mutable *live* topology (the authoritative twin state).
    * Snapshot history for diffing.
    * Change-impact analysis.
    * RCA correlation.
    * Audit trail.

    Example::

        twin = DigitalTwinEngine()
        twin.load_topology("network.json")
        twin.ingest_config("devices.yaml")
        result = twin.simulate_change("change.yaml")
        rca    = twin.diagnose("events.yaml")
    """

    def __init__(
        self,
        *,
        audit_log: str | Path | None = None,
    ) -> None:
        self._topology: Topology | None = None
        self._snapshots: list[TopologySnapshot] = []
        self._audit = AuditTrail(log_file=audit_log)

    # ── Properties ───────────────────────────────────────

    @property
    def topology(self) -> Topology:
        if self._topology is None:
            raise RuntimeError("No topology loaded. Call load_topology() first.")
        return self._topology

    @property
    def audit(self) -> AuditTrail:
        return self._audit

    @property
    def snapshots(self) -> list[TopologySnapshot]:
        return list(self._snapshots)

    # ── Topology loading ─────────────────────────────────

    def load_topology(self, path: str | Path) -> Topology:
        """Load a topology from JSON and take an initial snapshot.

        Args:
            path: Path to the topology JSON file.

        Returns:
            The loaded ``Topology``.
        """
        p = Path(path)
        self._topology = Topology.load(p)

        self._audit.record(
            AuditAction.TOPOLOGY_MUTATION,
            actor="system",
            source=str(p),
            explanation=f"Loaded topology from {p.name}",
            details={
                "nodes": self._topology.node_count,
                "edges": self._topology.edge_count,
            },
        )

        self._take_snapshot(label="initial_load")
        logger.info(
            "Topology loaded",
            path=str(p),
            nodes=self._topology.node_count,
            edges=self._topology.edge_count,
        )
        return self._topology

    def set_topology(self, topology: Topology) -> None:
        """Programmatically set the topology (e.g. from a generator)."""
        self._topology = topology
        self._take_snapshot(label="programmatic_set")

    # ── Config ingestion ─────────────────────────────────

    def ingest_config(self, path: str | Path) -> list[str]:
        """Ingest device configurations and apply to the live topology.

        Args:
            path: Path to a YAML/JSON device config file.

        Returns:
            List of device hostnames that were applied.
        """
        configs = ConfigParser.load_device_configs(path)
        hostnames = [c.hostname for c in configs]

        ConfigParser.apply_device_configs(self.topology, configs)

        self._audit.record(
            AuditAction.CONFIG_CHANGE,
            actor="system",
            source=str(path),
            details={"devices": hostnames},
            explanation=(
                f"Ingested {len(configs)} device config(s) from "
                f"{Path(path).name}: {', '.join(hostnames)}"
            ),
        )

        self._take_snapshot(label="config_ingestion")
        return hostnames

    # ── Change-impact simulation ─────────────────────────

    def simulate_change(
        self,
        change: ConfigChange | str | Path,
        *,
        weight: str = "latency",
    ) -> BlastRadius:
        """Simulate a proposed change and compute blast-radius.

        Args:
            change: A ``ConfigChange`` object or path to a change YAML/JSON.
            weight: Edge weight attribute for path computation.

        Returns:
            A ``BlastRadius`` report.
        """
        if isinstance(change, (str, Path)):
            change = ConfigParser.load_change(change)

        sim = ChangeImpactSimulator(self.topology)
        result = sim.simulate(change, weight=weight)

        # Build counterfactual narrative
        counterfactual_text = self._build_counterfactual(result)

        self._audit.record(
            AuditAction.CONFIG_CHANGE,
            actor="system",
            details=result.to_dict(),
            explanation=(
                f"Change-impact simulation: "
                f"{result.newly_unreachable_pairs} pairs became unreachable, "
                f"{result.path_changed_pairs} paths changed, "
                f"computed in {result.computation_ms:.1f} ms."
            ),
            counterfactual=counterfactual_text,
            counterfactual_data=result.to_dict(),
        )

        return result

    # ── Root-cause analysis ──────────────────────────────

    def diagnose(
        self,
        events: list[NetworkEvent] | str | Path,
    ) -> RCAResult:
        """Run root-cause analysis on a set of events.

        Args:
            events: A list of ``NetworkEvent`` objects or path to events file.

        Returns:
            An ``RCAResult`` report.
        """
        if isinstance(events, (str, Path)):
            events = load_events(events)

        correlator = RCACorrelator(self.topology)
        result = correlator.diagnose(events)

        self._audit.record(
            AuditAction.RCA_DIAGNOSIS,
            actor="system",
            details=result.to_dict(),
            explanation=result.root_cause_summary,
        )

        return result

    # ── Analytical queries ───────────────────────────────

    def compute_reachability(self) -> dict[str, set[str]]:
        """Compute reachability from every node to every other node."""
        graph = AnalyticalEngine.get_active_graph(self.topology)
        return AnalyticalEngine.compute_reachability(graph)

    def compute_shortest_paths(
        self,
        weight: str = "latency",
    ) -> dict[str, dict[str, list[str]]]:
        """Compute all-pairs shortest paths on the active graph."""
        graph = AnalyticalEngine.get_active_graph(self.topology)
        return AnalyticalEngine.compute_all_pairs_shortest_paths(graph, weight)

    def health_summary(self) -> dict[str, Any]:
        """Return a snapshot of the network's health."""
        topo = self.topology
        graph = AnalyticalEngine.get_active_graph(topo)

        down_nodes = [
            n
            for n, d in topo.graph.nodes(data=True)
            if str(d.get("status", "up")).lower() == "down"
        ]
        down_edges = [
            (u, v)
            for u, v, d in topo.graph.edges(data=True)
            if str(d.get("status", "up")).lower() == "down"
        ]

        return {
            "total_nodes": topo.node_count,
            "total_edges": topo.edge_count,
            "active_nodes": graph.number_of_nodes(),
            "active_edges": graph.number_of_edges(),
            "down_nodes": down_nodes,
            "down_edges": [list(e) for e in down_edges],
            "is_strongly_connected": (
                graph.number_of_nodes() > 0
                and __import__("networkx").is_strongly_connected(graph)
            ),
            "audit_summary": self._audit.summary(),
        }

    # ── Snapshot management ──────────────────────────────

    def _take_snapshot(self, label: str = "") -> TopologySnapshot:
        topo = self.topology
        graph = AnalyticalEngine.get_active_graph(topo)

        snap = TopologySnapshot(
            timestamp=time.time(),
            node_count=topo.node_count,
            edge_count=topo.edge_count,
            active_nodes=graph.number_of_nodes(),
            active_edges=graph.number_of_edges(),
            reachability_matrix=AnalyticalEngine.compute_reachability(graph),
            metadata={"label": label},
        )
        self._snapshots.append(snap)
        return snap

    @staticmethod
    def _build_counterfactual(result: BlastRadius) -> str:
        """Generate a human-readable counterfactual narrative."""
        lines = ["Counterfactual Analysis:"]

        if result.newly_unreachable_pairs == 0 and result.path_changed_pairs == 0:
            lines.append(
                "  If this change were NOT applied, the network state "
                "would remain identical. No traffic disruption expected."
            )
            return "\n".join(lines)

        lines.append(
            f"  If this change IS applied, {result.newly_unreachable_pairs} "
            f"node pairs lose reachability and {result.path_changed_pairs} "
            f"flows will be rerouted."
        )

        if result.max_latency_increase > 0:
            lines.append(
                f"  Maximum latency increase: +{result.max_latency_increase:.2f} ms "
                f"(avg before: {result.avg_latency_before:.2f} ms → "
                f"avg after: {result.avg_latency_after:.2f} ms)."
            )

        if result.affected_nodes:
            lines.append(
                f"  Blast radius: {len(result.affected_nodes)} node(s) affected."
            )

        lines.append(
            "  If this change is NOT applied, these flows continue "
            "on their current paths with their current latencies."
        )

        return "\n".join(lines)
