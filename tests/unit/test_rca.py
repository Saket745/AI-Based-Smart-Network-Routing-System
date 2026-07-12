"""Unit tests for the RCA (Root-Cause Analysis) correlator and event system."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
import yaml

if TYPE_CHECKING:
    from pathlib import Path

from nroute.core.topology import Topology
from nroute.exceptions import SimulationError
from nroute.simulation.rca import (
    EventCategory,
    EventSeverity,
    NetworkEvent,
    RCACorrelator,
    RCAResult,
    classify_event,
    load_events,
)

# ── classify_event Tests ─────────────────────────────────────


def test_classify_event_already_set() -> None:
    """If category is not UNKNOWN, classify_event should return it unchanged."""
    event = NetworkEvent(
        event_type="bgp_session_down",
        category=EventCategory.SYSLOG,
        severity=EventSeverity.WARNING,
    )
    res = classify_event(event)
    assert res.category == EventCategory.SYSLOG
    assert res.severity == EventSeverity.WARNING


@pytest.mark.parametrize(
    ("event_type", "expected_cat", "expected_sev"),
    [
        # Routing (Priority 1)
        ("bgp_session_down", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("BGP_WITHDRAWAL", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("  bgp_down  ", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("bgp_flap", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("ospf_adjacency_loss", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("ospf_nbr_down", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("ospf_neighbor_down", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("ospf_recalculation", EventCategory.ROUTING, EventSeverity.ERROR),
        ("ospf_spf", EventCategory.ROUTING, EventSeverity.ERROR),
        ("ospf_route_change", EventCategory.ROUTING, EventSeverity.ERROR),
        ("ecmp_change", EventCategory.ROUTING, EventSeverity.WARNING),
        ("route_change", EventCategory.ROUTING, EventSeverity.WARNING),
        ("routing_table_change", EventCategory.ROUTING, EventSeverity.WARNING),
        # Interface (Priority 2)
        ("link_down", EventCategory.INTERFACE, EventSeverity.CRITICAL),
        ("interface_down", EventCategory.INTERFACE, EventSeverity.CRITICAL),
        ("port_down", EventCategory.INTERFACE, EventSeverity.CRITICAL),
        ("link_up", EventCategory.INTERFACE, EventSeverity.INFO),
        ("interface_up", EventCategory.INTERFACE, EventSeverity.INFO),
        ("port_up", EventCategory.INTERFACE, EventSeverity.INFO),
        ("interface_flap", EventCategory.INTERFACE, EventSeverity.ERROR),
        ("link_flap", EventCategory.INTERFACE, EventSeverity.ERROR),
        ("crc_error", EventCategory.INTERFACE, EventSeverity.WARNING),
        ("crc_errors", EventCategory.INTERFACE, EventSeverity.WARNING),
        ("frame_errors", EventCategory.INTERFACE, EventSeverity.WARNING),
        ("port_disabled", EventCategory.INTERFACE, EventSeverity.WARNING),
        # Syslog (Priority 3)
        ("syslog_critical", EventCategory.SYSLOG, EventSeverity.CRITICAL),
        ("syslog_error", EventCategory.SYSLOG, EventSeverity.ERROR),
        ("syslog_warning", EventCategory.SYSLOG, EventSeverity.WARNING),
        # Default / No match
        ("unknown_weird_event", EventCategory.UNKNOWN, EventSeverity.INFO),
    ],
)
def test_classify_event_rules(
    event_type: str, expected_cat: EventCategory, expected_sev: EventSeverity
) -> None:
    """Test all heuristics matching from _TYPE_RULES."""
    event = NetworkEvent(event_type=event_type)
    res = classify_event(event)
    assert res.category == expected_cat
    assert res.severity == expected_sev


# ── NetworkEvent & RCAResult Tests ──────────────────────────


def test_network_event_priority() -> None:
    """Check priority returns expected values for categories."""
    assert NetworkEvent(category=EventCategory.ROUTING).priority == 1
    assert NetworkEvent(category=EventCategory.INTERFACE).priority == 2
    assert NetworkEvent(category=EventCategory.SYSLOG).priority == 3
    assert NetworkEvent(category=EventCategory.UNKNOWN).priority == 99


def test_rca_result_to_dict_empty() -> None:
    """Check serialization of RCAResult with no root cause."""
    res = RCAResult(root_cause=None, root_cause_summary="None")
    d = res.to_dict()
    assert d["root_cause"] is None
    assert d["root_cause_summary"] == "None"
    assert d["correlation_chain"] == []
    assert d["affected_nodes"] == []
    assert d["affected_edges"] == []
    assert d["total_events"] == 0


def test_rca_result_to_dict_with_cause() -> None:
    """Check serialization of RCAResult with full properties."""
    evt = NetworkEvent(
        event_id="evt_123",
        timestamp=45.6,
        node_id="NodeA",
        interface="eth0",
        peer_node="NodeB",
        event_type="link_down",
        category=EventCategory.INTERFACE,
        severity=EventSeverity.CRITICAL,
        message="Link cut",
    )
    res = RCAResult(
        root_cause=evt,
        root_cause_summary="Some Summary",
        correlation_chain=[evt],
        affected_nodes={"NodeA", "NodeB"},
        affected_edges={("NodeA", "NodeB"), ("NodeB", "NodeA")},
        total_events=1,
    )
    d = res.to_dict()
    assert d["root_cause"] is not None
    assert d["root_cause"]["event_id"] == "evt_123"
    assert d["root_cause"]["timestamp"] == 45.6
    assert d["root_cause"]["category"] == "interface"
    assert d["root_cause"]["severity"] == "critical"
    assert d["root_cause_summary"] == "Some Summary"
    assert d["affected_nodes"] == ["NodeA", "NodeB"]
    # affected_edges are sorted tuples converted to list
    assert d["affected_edges"] == [["NodeA", "NodeB"], ["NodeB", "NodeA"]]
    assert d["total_events"] == 1


# ── load_events Tests ────────────────────────────────────────


def test_load_events_not_found() -> None:
    """Should raise SimulationError if file doesn't exist."""
    with pytest.raises(SimulationError, match="Events file not found"):
        load_events("non_existent_file_path_12345.json")


def test_load_events_unsupported_suffix(tmp_path: Path) -> None:
    """Should raise SimulationError if suffix is unsupported."""
    f = tmp_path / "events.txt"
    f.write_text("dummy")
    with pytest.raises(SimulationError, match="Unsupported events file extension"):
        load_events(f)


def test_load_events_invalid_json(tmp_path: Path) -> None:
    """Should raise SimulationError if JSON is malformed."""
    f = tmp_path / "events.json"
    f.write_text("{invalid json")
    with pytest.raises(SimulationError, match="Failed to parse events file"):
        load_events(f)


def test_load_events_invalid_yaml(tmp_path: Path) -> None:
    """Should raise SimulationError if YAML is malformed."""
    f = tmp_path / "events.yaml"
    f.write_text("invalid: - [ : - yaml")
    with pytest.raises(SimulationError, match="Failed to parse events file"):
        load_events(f)


def test_load_events_not_list_or_dict(tmp_path: Path) -> None:
    """Should raise SimulationError if loaded file structure is a plain string/number."""
    f = tmp_path / "events.json"
    f.write_text("123")
    with pytest.raises(SimulationError, match="Events file must be a list of event records"):
        load_events(f)


def test_load_events_dict_missing_keys(tmp_path: Path) -> None:
    """Should raise SimulationError if dictionary lacks events/alarms/records keys."""
    f = tmp_path / "events.json"
    f.write_text('{"other_key": []}')
    with pytest.raises(
        SimulationError, match="Events file must be a list or contain an 'events' key"
    ):
        load_events(f)


def test_load_events_dict_wrappers(tmp_path: Path) -> None:
    """Check 'events', 'alarms', 'records' top-level keys."""
    evt_data = [{"event_id": "e1", "event_type": "link_down"}]

    # Test "events" key
    f1 = tmp_path / "f1.json"
    f1.write_text(json.dumps({"events": evt_data}))
    assert len(load_events(f1)) == 1

    # Test "alarms" key
    f2 = tmp_path / "f2.json"
    f2.write_text(json.dumps({"alarms": evt_data}))
    assert len(load_events(f2)) == 1

    # Test "records" key
    f3 = tmp_path / "f3.json"
    f3.write_text(json.dumps({"records": evt_data}))
    assert len(load_events(f3)) == 1


def test_load_events_skips_non_dict_elements(tmp_path: Path) -> None:
    """Any non-dictionary item in the events list is ignored."""
    f = tmp_path / "events.json"
    f.write_text(json.dumps([123, {"event_id": "e1"}, "string"]))
    evts = load_events(f)
    assert len(evts) == 1
    assert evts[0].event_id == "e1"


def test_load_events_malformed_fields_resilience(tmp_path: Path) -> None:
    """Verify loading is resilient to malformed/invalid field types or formats."""
    # Test fallback to EventCategory.UNKNOWN / EventSeverity.INFO and default parsing
    f = tmp_path / "events.yaml"
    data = [
        {
            # timestamp not a float -> triggers Exception block in parsing
            "timestamp": "invalid_timestamp_string",
        },
        {
            "event_id": "ok_event",
            "category": "invalid_category",
            "severity": "invalid_severity",
        },
    ]
    f.write_text(yaml.safe_dump(data))
    evts = load_events(f)
    # The first one should have been skipped, the second one parsed with defaults
    assert len(evts) == 1
    assert evts[0].event_id == "ok_event"
    assert evts[0].category == EventCategory.UNKNOWN
    assert evts[0].severity == EventSeverity.INFO


# ── RCACorrelator Tests ──────────────────────────────────────


def test_rca_correlator_empty() -> None:
    """Diagnosing an empty list of events should return placeholder."""
    topo = Topology()
    correlator = RCACorrelator(topo)
    res = correlator.diagnose([])
    assert res.root_cause is None
    assert res.root_cause_summary == "No events provided."
    assert res.total_events == 0


def test_rca_correlator_neighbor_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure we survive exception when querying neighbors."""
    topo = Topology()
    topo.add_node("R1")
    topo.add_node("R2")
    topo.add_edge("R1", "R2")

    def mock_neighbors(*args: Any, **kwargs: Any) -> list[str]:
        raise ValueError("Simulated topology failure")

    monkeypatch.setattr(topo, "neighbors", mock_neighbors)

    events = [
        NetworkEvent(
            event_id="e1",
            timestamp=10.0,
            node_id="R1",
            peer_node="R2",
            event_type="link_down",
            category=EventCategory.INTERFACE,
        )
    ]
    correlator = RCACorrelator(topo)
    res = correlator.diagnose(events)
    # We should still diagnose without crashing
    assert res.root_cause is not None
    assert res.root_cause.event_id == "e1"
    # Neighbors failure means downstream_nodes is just {"R1", "R2"}
    assert len(res.correlation_chain) == 1


def test_rca_correlator_priority_and_timestamp_sorting() -> None:
    """Verify that earlier, higher priority events are isolated as root cause."""
    topo = Topology()
    topo.add_node("R1")
    topo.add_node("R2")
    topo.add_edge("R1", "R2")

    # Order of events:
    # 1. Interface event @ t=5.0
    # 2. Routing event @ t=6.0 (higher priority than interface, so should win over 1 even though later)
    # 3. Routing event @ t=7.0 (same priority as 2, but later, so 2 wins over 3)
    events = [
        NetworkEvent(
            event_id="e1",
            timestamp=5.0,
            node_id="R1",
            event_type="link_down",
            category=EventCategory.INTERFACE,
        ),
        NetworkEvent(
            event_id="e3",
            timestamp=7.0,
            node_id="R1",
            event_type="bgp_withdrawal",
            category=EventCategory.ROUTING,
        ),
        NetworkEvent(
            event_id="e2",
            timestamp=6.0,
            node_id="R1",
            event_type="bgp_session_down",
            category=EventCategory.ROUTING,
        ),
    ]

    correlator = RCACorrelator(topo)
    res = correlator.diagnose(events)
    assert res.root_cause is not None
    assert res.root_cause.event_id == "e2"


def test_rca_correlator_same_priority_earlier_wins() -> None:
    """If two events have the same priority, the earlier one is chosen as root cause."""
    topo = Topology()
    topo.add_node("R1")

    events = [
        NetworkEvent(
            event_id="e2",
            timestamp=12.0,
            node_id="R1",
            event_type="bgp_withdrawal",
            category=EventCategory.ROUTING,
        ),
        NetworkEvent(
            event_id="e1",
            timestamp=10.0,
            node_id="R1",
            event_type="bgp_session_down",
            category=EventCategory.ROUTING,
        ),
    ]

    correlator = RCACorrelator(topo)
    res = correlator.diagnose(events)
    assert res.root_cause is not None
    assert res.root_cause.event_id == "e1"


def test_rca_correlator_same_priority_earlier_wins_dynamic() -> None:
    """Test same priority earlier wins with dynamic timestamps to cover line 306."""

    class DynamicEvent(NetworkEvent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._reads = 0

        @property
        def timestamp(self) -> float:
            self._reads += 1
            if self._reads <= 2:
                return 10.0
            return 20.0

        @timestamp.setter
        def timestamp(self, val: float) -> None:
            pass

    topo = Topology()
    topo.add_node("R1")
    e1 = DynamicEvent(event_id="e1", event_type="bgp_session_down", category=EventCategory.ROUTING)
    e2 = NetworkEvent(
        event_id="e2", timestamp=12.0, event_type="bgp_withdrawal", category=EventCategory.ROUTING
    )

    correlator = RCACorrelator(topo)
    res = correlator.diagnose([e1, e2])
    assert res.root_cause is not None
    assert res.root_cause.event_id == "e2"


def test_rca_correlator_summary_detail() -> None:
    """Verify summary includes peer details, message, and multiple chain links."""
    topo = Topology()
    topo.add_node("R1")
    topo.add_node("R2")
    topo.add_edge("R1", "R2")

    events = [
        NetworkEvent(
            event_id="e1",
            timestamp=1.0,
            node_id="R1",
            peer_node="R2",
            event_type="bgp_session_down",
            category=EventCategory.ROUTING,
            message="Lost Keepalive",
        ),
        NetworkEvent(
            event_id="e2",
            timestamp=2.0,
            node_id="R2",
            event_type="route_change",
            category=EventCategory.ROUTING,
        ),
    ]

    correlator = RCACorrelator(topo)
    res = correlator.diagnose(events)
    summary = res.root_cause_summary

    assert "Root Cause: bgp_session_down on node 'R1' (peer: 'R2')" in summary
    assert "Detail: Lost Keepalive" in summary
    assert "Correlation Chain (2 events):" in summary
    assert "└─ [routing] route_change on 'R2' @ t=2.0" in summary
