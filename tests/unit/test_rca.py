"""Unit tests for the Root-Cause Analysis (RCA) correlator."""

from __future__ import annotations

import json
from typing import Any

import pytest
import yaml

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


def test_network_event_priority() -> None:
    """Test that NetworkEvent priority is correctly derived from category."""
    assert NetworkEvent(category=EventCategory.ROUTING).priority == 1
    assert NetworkEvent(category=EventCategory.INTERFACE).priority == 2
    assert NetworkEvent(category=EventCategory.SYSLOG).priority == 3
    assert NetworkEvent(category=EventCategory.UNKNOWN).priority == 99


@pytest.mark.parametrize(
    "event_type, expected_cat, expected_sev",
    [
        ("bgp_session_down", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("BGP_DOWN", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("  ospf_adjacency_loss  ", EventCategory.ROUTING, EventSeverity.CRITICAL),
        ("ospf_spf", EventCategory.ROUTING, EventSeverity.ERROR),
        ("route_change", EventCategory.ROUTING, EventSeverity.WARNING),
        ("link_down", EventCategory.INTERFACE, EventSeverity.CRITICAL),
        ("interface_up", EventCategory.INTERFACE, EventSeverity.INFO),
        ("link_flap", EventCategory.INTERFACE, EventSeverity.ERROR),
        ("crc_errors", EventCategory.INTERFACE, EventSeverity.WARNING),
        ("port_disabled", EventCategory.INTERFACE, EventSeverity.WARNING),
        ("syslog_critical", EventCategory.SYSLOG, EventSeverity.CRITICAL),
        ("syslog_error", EventCategory.SYSLOG, EventSeverity.ERROR),
        ("syslog_warning", EventCategory.SYSLOG, EventSeverity.WARNING),
        ("unknown_type", EventCategory.UNKNOWN, EventSeverity.INFO),
    ],
)
def test_classify_event_mapping(
    event_type: str, expected_cat: EventCategory, expected_sev: EventSeverity
) -> None:
    """Test that classify_event correctly maps various event types."""
    event = NetworkEvent(event_type=event_type)
    classified = classify_event(event)
    assert classified.category == expected_cat
    assert classified.severity == expected_sev


def test_classify_event_already_set() -> None:
    """Test that classify_event does not override already set category."""
    event = NetworkEvent(
        event_type="bgp_session_down",
        category=EventCategory.INTERFACE,
        severity=EventSeverity.INFO,
    )
    classified = classify_event(event)
    assert classified.category == EventCategory.INTERFACE
    assert classified.severity == EventSeverity.INFO


# ── load_events tests ─────────────────────────────────────────


def test_load_events_yaml(tmp_path: Any) -> None:
    """Test loading events from a YAML file."""
    events_data = [
        {"event_type": "link_down", "node_id": "A"},
        {"event_type": "bgp_session_down", "node_id": "B", "category": "routing"},
    ]
    p = tmp_path / "events.yaml"
    with open(p, "w") as f:
        yaml.dump(events_data, f)

    events = load_events(p)
    assert len(events) == 2
    assert events[0].event_type == "link_down"
    assert events[0].category == EventCategory.INTERFACE
    assert events[1].event_type == "bgp_session_down"
    assert events[1].category == EventCategory.ROUTING


def test_load_events_json(tmp_path: Any) -> None:
    """Test loading events from a JSON file with wrapper key."""
    events_data = {
        "events": [
            {"event_id": "e1", "event_type": "port_down", "node_id": "C"},
        ]
    }
    p = tmp_path / "events.json"
    with open(p, "w") as f:
        json.dump(events_data, f)

    events = load_events(p)
    assert len(events) == 1
    assert events[0].event_id == "e1"
    assert events[0].event_type == "port_down"


def test_load_events_unsupported_extension(tmp_path: Any) -> None:
    """Test that loading from unsupported extension raises SimulationError."""
    p = tmp_path / "events.txt"
    p.touch()
    with pytest.raises(SimulationError, match="Unsupported events file extension"):
        load_events(p)


def test_load_events_not_found() -> None:
    """Test that loading non-existent file raises SimulationError."""
    with pytest.raises(SimulationError, match="Events file not found"):
        load_events("non_existent_file.yaml")


def test_load_events_invalid_format(tmp_path: Any) -> None:
    """Test that invalid format (not a list or dict with events) raises error."""
    p = tmp_path / "events.yaml"
    with open(p, "w") as f:
        yaml.dump("just a string", f)

    with pytest.raises(SimulationError, match="Events file must be a list"):
        load_events(p)

    # Test dict without valid key
    with open(p, "w") as f:
        yaml.dump({"wrong_key": []}, f)
    with pytest.raises(SimulationError, match="Events file must be a list or contain an 'events' key"):
        load_events(p)


def test_load_events_malformed_yaml(tmp_path: Any) -> None:
    """Test that malformed YAML raises SimulationError."""
    p = tmp_path / "malformed.yaml"
    with open(p, "w") as f:
        f.write(" - [ unclosed bracket")

    with pytest.raises(SimulationError, match="Failed to parse events file"):
        load_events(p)


def test_load_events_skip_invalid_item(tmp_path: Any) -> None:
    """Test skipping non-dict items and unparseable events."""
    events_data = [
        "not a dict",
        {"event_type": "link_up", "timestamp": "invalid_float"},
        {"event_type": "link_down", "timestamp": 10.0},
    ]
    p = tmp_path / "events.yaml"
    with open(p, "w") as f:
        yaml.dump(events_data, f)

    events = load_events(p)
    assert len(events) == 1
    assert events[0].event_type == "link_down"


# ── RCACorrelator tests ───────────────────────────────────────


def test_rca_correlator_diagnose(small_graph_data: dict[str, Any]) -> None:
    """Test that RCACorrelator correctly identifies the root cause."""
    from nroute.core.topology import Topology

    # Translate small_graph_data to Topology expected format
    edges = []
    for edge in small_graph_data.get("edges", []):
        edges.append(
            {
                "source": edge.get("src"),
                "target": edge.get("dst"),
                "bandwidth": edge.get("bandwidth"),
                "latency": edge.get("latency"),
                "status": edge.get("status"),
            }
        )
    topo = Topology.from_dict({"nodes": small_graph_data.get("nodes", []), "edges": edges})
    correlator = RCACorrelator(topo)

    # Scenario: Link down A->B causes BGP session down
    events = [
        NetworkEvent(
            event_id="e1",
            timestamp=10.0,
            node_id="A",
            peer_node="B",
            event_type="link_down",
        ),
        NetworkEvent(
            event_id="e2",
            timestamp=12.0,
            node_id="A",
            peer_node="B",
            event_type="bgp_session_down",
        ),
        NetworkEvent(
            event_id="e3",
            timestamp=15.0,
            node_id="C",
            event_type="syslog_warning",
        ),
    ]
    # Pre-classify
    for e in events:
        classify_event(e)

    result = correlator.diagnose(events)

    # Root cause should be e2 (bgp_session_down) because it has higher priority (ROUTING=1)
    # than link_down (INTERFACE=2), even though link_down was earlier.
    assert result.root_cause is not None
    assert result.root_cause.event_id == "e2"
    assert "bgp_session_down" in result.root_cause_summary
    assert "A" in result.affected_nodes
    assert "B" in result.affected_nodes
    assert "C" in result.affected_nodes
    assert ("A", "B") in result.affected_edges

    # Check correlation chain
    # e1 (link_down on A/B) should be in chain because it involves A or B
    # e3 (syslog on C) should NOT be in chain if C is not a neighbor of A or B.
    # Neighbors of A are B, C.
    # So C IS a neighbor of A.
    assert any(e.event_id == "e1" for e in result.correlation_chain)
    assert any(e.event_id == "e3" for e in result.correlation_chain)


def test_rca_correlator_same_priority_earlier_timestamp(small_graph_data: dict[str, Any]) -> None:
    """Test that for same priority, the earlier event is chosen as root cause."""
    from nroute.core.topology import Topology
    topo = Topology()
    correlator = RCACorrelator(topo)

    events = [
        NetworkEvent(event_id="e1", timestamp=20.0, event_type="link_down", category=EventCategory.INTERFACE),
        NetworkEvent(event_id="e2", timestamp=10.0, event_type="port_down", category=EventCategory.INTERFACE, message="Critical port"),
    ]
    result = correlator.diagnose(events)
    assert result.root_cause.event_id == "e2"
    assert "Critical port" in result.root_cause_summary


def test_rca_correlator_priority_precedence(small_graph_data: dict[str, Any]) -> None:
    """Test that higher priority (lower number) takes precedence over earlier timestamp."""
    from nroute.core.topology import Topology
    topo = Topology()
    correlator = RCACorrelator(topo)

    events = [
        NetworkEvent(event_id="e1", timestamp=10.0, event_type="syslog_error", category=EventCategory.SYSLOG),    # p=3
        NetworkEvent(event_id="e2", timestamp=15.0, event_type="link_down", category=EventCategory.INTERFACE),    # p=2
        NetworkEvent(event_id="e3", timestamp=20.0, event_type="bgp_down", category=EventCategory.ROUTING),       # p=1
    ]
    # Current implementation with 'break' might fail to find e3 if it stops at e2.
    result = correlator.diagnose(events)

    # If the goal is "highest priority", it should be e3.
    # If it stops at the first improvement, it will be e2.
    assert result.root_cause.event_id == "e3"


def test_rca_correlator_no_events(small_graph_data: dict[str, Any]) -> None:
    """Test RCA with no events."""
    from nroute.core.topology import Topology

    topo = Topology()
    correlator = RCACorrelator(topo)
    result = correlator.diagnose([])
    assert result.root_cause is None
    assert "No events provided" in result.root_cause_summary


def test_rca_result_to_dict() -> None:
    """Test RCAResult.to_dict serialization."""
    root = NetworkEvent(
        event_id="e1",
        timestamp=10.0,
        node_id="A",
        event_type="link_down",
        category=EventCategory.INTERFACE,
        severity=EventSeverity.CRITICAL,
    )
    result = RCAResult(
        root_cause=root,
        root_cause_summary="Summary",
        correlation_chain=[root],
        affected_nodes={"A", "B"},
        affected_edges={("A", "B")},
        total_events=1,
    )

    d = result.to_dict()
    assert d["root_cause"]["event_id"] == "e1"
    assert d["root_cause_summary"] == "Summary"
    assert d["affected_nodes"] == ["A", "B"]
    assert d["affected_edges"] == [["A", "B"]]
