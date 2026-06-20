"""Topology-aware Root-Cause Analysis (RCA) correlator.

Ingests structured alarm / event streams and correlates them against the
network topology graph to identify the most probable root cause.

Phase 1 priorities:
  * Priority 1 — Routing events (BGP session down, OSPF adjacency loss, etc.)
  * Priority 2 — Interface events (link down/up, flap, CRC errors)
  * Priority 3 — Critical syslog events

The correlator builds an event-dependency graph and walks it backward
to isolate root failures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from nroute.core.topology import Topology
from nroute.exceptions import SimulationError
from nroute.utils.logging import get_logger

logger = get_logger(__name__)


# ── Event models ─────────────────────────────────────────────


class EventSeverity(str, Enum):
    """Alarm / event severity."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class EventCategory(str, Enum):
    """Category for RCA prioritisation."""

    ROUTING = "routing"
    INTERFACE = "interface"
    SYSLOG = "syslog"
    UNKNOWN = "unknown"


# Priority mapping  (lower = higher priority)
_CATEGORY_PRIORITY: dict[EventCategory, int] = {
    EventCategory.ROUTING: 1,
    EventCategory.INTERFACE: 2,
    EventCategory.SYSLOG: 3,
    EventCategory.UNKNOWN: 99,
}


@dataclass
class NetworkEvent:
    """A single alarm / event record."""

    event_id: str = ""
    timestamp: float = 0.0
    node_id: str = ""
    interface: str = ""
    peer_node: str = ""
    event_type: str = ""
    category: EventCategory = EventCategory.UNKNOWN
    severity: EventSeverity = EventSeverity.INFO
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def priority(self) -> int:
        return _CATEGORY_PRIORITY.get(self.category, 99)


@dataclass
class RCAResult:
    """Root-cause analysis result."""

    root_cause: NetworkEvent | None = None
    root_cause_summary: str = ""
    correlation_chain: list[NetworkEvent] = field(default_factory=list)
    affected_nodes: set[str] = field(default_factory=set)
    affected_edges: set[tuple[str, str]] = field(default_factory=set)
    total_events: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""

        def _evt(e: NetworkEvent) -> dict[str, Any]:
            return {
                "event_id": e.event_id,
                "timestamp": e.timestamp,
                "node_id": e.node_id,
                "interface": e.interface,
                "peer_node": e.peer_node,
                "event_type": e.event_type,
                "category": e.category.value,
                "severity": e.severity.value,
                "message": e.message,
            }

        return {
            "root_cause": _evt(self.root_cause) if self.root_cause else None,
            "root_cause_summary": self.root_cause_summary,
            "correlation_chain": [_evt(e) for e in self.correlation_chain],
            "affected_nodes": sorted(self.affected_nodes),
            "affected_edges": [list(e) for e in sorted(self.affected_edges)],
            "total_events": self.total_events,
        }


# ── Event classification heuristics ──────────────────────────

# Maps event_type substrings to categories and severities
_TYPE_RULES: list[tuple[list[str], EventCategory, EventSeverity]] = [
    # Routing events (Priority 1)
    (["bgp_session_down", "bgp_withdrawal", "bgp_down", "bgp_flap"],
     EventCategory.ROUTING, EventSeverity.CRITICAL),
    (["ospf_adjacency_loss", "ospf_nbr_down", "ospf_neighbor_down"],
     EventCategory.ROUTING, EventSeverity.CRITICAL),
    (["ospf_recalculation", "ospf_spf", "ospf_route_change"],
     EventCategory.ROUTING, EventSeverity.ERROR),
    (["ecmp_change", "route_change", "routing_table_change"],
     EventCategory.ROUTING, EventSeverity.WARNING),
    # Interface events (Priority 2)
    (["link_down", "interface_down", "port_down"],
     EventCategory.INTERFACE, EventSeverity.CRITICAL),
    (["link_up", "interface_up", "port_up"],
     EventCategory.INTERFACE, EventSeverity.INFO),
    (["interface_flap", "link_flap"],
     EventCategory.INTERFACE, EventSeverity.ERROR),
    (["crc_error", "crc_errors", "frame_errors"],
     EventCategory.INTERFACE, EventSeverity.WARNING),
    (["port_disabled"],
     EventCategory.INTERFACE, EventSeverity.WARNING),
    # Syslog events (Priority 3)
    (["syslog_critical"],
     EventCategory.SYSLOG, EventSeverity.CRITICAL),
    (["syslog_error"],
     EventCategory.SYSLOG, EventSeverity.ERROR),
    (["syslog_warning"],
     EventCategory.SYSLOG, EventSeverity.WARNING),
]


def classify_event(event: NetworkEvent) -> NetworkEvent:
    """Set category and severity based on event_type if not already set."""
    if event.category != EventCategory.UNKNOWN:
        return event

    et_lower = event.event_type.lower().strip()
    for keywords, category, severity in _TYPE_RULES:
        if any(kw in et_lower for kw in keywords):
            event.category = category
            event.severity = severity
            return event

    return event


# ── Event loading ────────────────────────────────────────────


def load_events(path: str | Path) -> list[NetworkEvent]:
    """Load alarm/event records from a YAML or JSON file.

    Expected format — a list of objects with keys like:
    ``event_id``, ``timestamp``, ``node_id``, ``interface``,
    ``peer_node``, ``event_type``, ``category``, ``severity``, ``message``.
    """
    p = Path(path)
    if not p.is_file():
        raise SimulationError(f"Events file not found: {path}")

    try:
        with open(p, encoding="utf-8") as f:
            if p.suffix.lower() in {".yaml", ".yml"}:
                raw = yaml.safe_load(f)
            elif p.suffix.lower() == ".json":
                raw = json.load(f)
            else:
                raise SimulationError(
                    f"Unsupported events file extension '{p.suffix}'."
                )
    except Exception as exc:
        if isinstance(exc, SimulationError):
            raise
        raise SimulationError(f"Failed to parse events file: {exc}") from exc

    if not isinstance(raw, list):
        # Tolerate a top-level wrapper key
        if isinstance(raw, dict):
            for key in ("events", "alarms", "records"):
                if key in raw and isinstance(raw[key], list):
                    raw = raw[key]
                    break
            else:
                raise SimulationError(
                    "Events file must be a list or contain an 'events' key."
                )
        else:
            raise SimulationError("Events file must be a list of event records.")

    events: list[NetworkEvent] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        try:
            cat = item.get("category", "unknown")
            sev = item.get("severity", "info")
            evt = NetworkEvent(
                event_id=str(item.get("event_id", f"evt_{idx}")),
                timestamp=float(item.get("timestamp", idx)),
                node_id=str(item.get("node_id", "")),
                interface=str(item.get("interface", "")),
                peer_node=str(item.get("peer_node", "")),
                event_type=str(item.get("event_type", "")),
                category=EventCategory(cat) if cat in EventCategory.__members__.values() else EventCategory.UNKNOWN,
                severity=EventSeverity(sev) if sev in EventSeverity.__members__.values() else EventSeverity.INFO,
                message=str(item.get("message", "")),
                raw=item,
            )
            events.append(classify_event(evt))
        except Exception:
            logger.warning("Skipping unparseable event", index=idx)

    return events


# ── RCA Correlator ───────────────────────────────────────────


class RCACorrelator:
    """Topology-aware root-cause correlator.

    Correlation pipeline::

        Fiber Cut → Interface Down → OSPF Adjacency Loss →
        Route Recompute → Traffic Shift → Latency Spike

    The correlator:
    1. Sorts events by timestamp.
    2. Groups co-located / related events.
    3. Finds the earliest, highest-priority event whose topology
       position can explain the downstream symptoms.
    """

    def __init__(self, topology: Topology) -> None:
        self.topology = topology

    def diagnose(self, events: list[NetworkEvent]) -> RCAResult:
        """Run root-cause diagnosis over a list of events.

        Args:
            events: List of ``NetworkEvent`` objects (pre-classified).

        Returns:
            An ``RCAResult`` with root cause, correlation chain, and
            affected graph elements.
        """
        if not events:
            return RCAResult(root_cause_summary="No events provided.")

        result = RCAResult(total_events=len(events))

        # 1. Sort by timestamp, then by priority (routing > interface > syslog)
        sorted_events = sorted(
            events,
            key=lambda e: (e.timestamp, e.priority),
        )

        # 2. Build affected-node / edge sets
        for evt in sorted_events:
            if evt.node_id:
                result.affected_nodes.add(evt.node_id)
            if evt.peer_node:
                result.affected_nodes.add(evt.peer_node)
            if evt.node_id and evt.peer_node:
                result.affected_edges.add((evt.node_id, evt.peer_node))

        # 3. Walk events to find the root cause
        #    The root cause is the earliest event on the highest-priority
        #    category that can topologically explain other events.
        root_candidate = sorted_events[0]

        # Try to find a higher-priority root
        for evt in sorted_events:
            if evt.priority < root_candidate.priority:
                root_candidate = evt
                break
            if (
                evt.priority == root_candidate.priority
                and evt.timestamp < root_candidate.timestamp
            ):
                root_candidate = evt

        result.root_cause = root_candidate

        # 4. Build correlation chain — events explained by the root cause
        chain: list[NetworkEvent] = [root_candidate]
        root_node = root_candidate.node_id
        root_peer = root_candidate.peer_node

        # Find downstream effects: events on the same node, adjacent nodes,
        # or nodes reachable through the failing link
        downstream_nodes = {root_node}
        if root_peer:
            downstream_nodes.add(root_peer)

        # Expand to topology neighbours of the failing link
        if root_node and root_node in self.topology.nodes:
            try:
                downstream_nodes.update(self.topology.neighbors(root_node))
            except Exception:
                pass
        if root_peer and root_peer in self.topology.nodes:
            try:
                downstream_nodes.update(self.topology.neighbors(root_peer))
            except Exception:
                pass

        for evt in sorted_events:
            if evt is root_candidate:
                continue
            if evt.node_id in downstream_nodes or evt.peer_node in downstream_nodes:
                chain.append(evt)

        result.correlation_chain = chain

        # 5. Generate human-readable summary
        result.root_cause_summary = self._build_summary(root_candidate, chain)

        logger.info(
            "RCA diagnosis complete",
            root_event=root_candidate.event_type,
            root_node=root_candidate.node_id,
            chain_length=len(chain),
            affected_nodes=len(result.affected_nodes),
        )

        return result

    @staticmethod
    def _build_summary(root: NetworkEvent, chain: list[NetworkEvent]) -> str:
        """Generate a human-readable root-cause summary."""
        lines = [
            f"Root Cause: {root.event_type} on node '{root.node_id}'",
        ]
        if root.peer_node:
            lines[0] += f" (peer: '{root.peer_node}')"
        if root.message:
            lines.append(f"  Detail: {root.message}")

        if len(chain) > 1:
            lines.append(f"\nCorrelation Chain ({len(chain)} events):")
            for i, evt in enumerate(chain):
                prefix = "  └─" if i == len(chain) - 1 else "  ├─"
                lines.append(
                    f"{prefix} [{evt.category.value}] {evt.event_type} "
                    f"on '{evt.node_id}' @ t={evt.timestamp}"
                )

        return "\n".join(lines)
