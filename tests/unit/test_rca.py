"""Unit tests for the Root-Cause Analysis (RCA) correlator."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sample_events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": "evt_1",
            "timestamp": 10.5,
            "node_id": "node_A",
            "event_type": "bgp_session_down",
            "message": "BGP session with neighbor 1.1.1.1 is down",
        },
        {
            "event_id": "evt_2",
            "timestamp": 11.0,
            "node_id": "node_A",
            "event_type": "interface_down",
            "interface": "eth0",
        },
    ]


def test_load_events_json_list(tmp_path: Path, sample_events: list[dict[str, Any]]) -> None:
    path = tmp_path / "events.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sample_events, f)

    events = load_events(path)
    assert len(events) == 2
    assert events[0].event_id == "evt_1"
    assert events[0].category == EventCategory.ROUTING
    assert events[0].severity == EventSeverity.CRITICAL


def test_load_events_json_dict(tmp_path: Path, sample_events: list[dict[str, Any]]) -> None:
    path = tmp_path / "events.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"events": sample_events}, f)

    events = load_events(path)
    assert len(events) == 2


def test_load_events_yaml_list(tmp_path: Path, sample_events: list[dict[str, Any]]) -> None:
    path = tmp_path / "events.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(sample_events, f)

    events = load_events(path)
    assert len(events) == 2
    assert events[1].event_id == "evt_2"
    assert events[1].category == EventCategory.INTERFACE
    assert events[1].severity == EventSeverity.CRITICAL


def test_load_events_yaml_dict_alarms(tmp_path: Path, sample_events: list[dict[str, Any]]) -> None:
    path = tmp_path / "events.yml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump({"alarms": sample_events}, f)

    events = load_events(path)
    assert len(events) == 2


def test_load_events_file_not_found() -> None:
    with pytest.raises(SimulationError, match="Events file not found"):
        load_events("non_existent_file.json")


def test_load_events_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "events.txt"
    path.write_text("some content")
    with pytest.raises(SimulationError, match="Unsupported events file extension"):
        load_events(path)


def test_load_events_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    path.write_text("{invalid json")
    with pytest.raises(SimulationError, match="Failed to parse events file"):
        load_events(path)


def test_load_events_invalid_structure(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"wrong_key": []}))
    with pytest.raises(
        SimulationError, match="Events file must be a list or contain an 'events' key"
    ):
        load_events(path)

    path.write_text(json.dumps(123))
    with pytest.raises(SimulationError, match="Events file must be a list of event records"):
        load_events(path)


def test_load_events_skip_unparseable(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    # One good, one bad (not a dict), one with invalid timestamp (to trigger exception in constructor)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"event_id": "good"}, "bad", {"timestamp": "invalid"}], f)

    events = load_events(path)
    assert len(events) == 1
    assert events[0].event_id == "good"


def test_classify_event_heuristics() -> None:
    # Test routing
    evt = NetworkEvent(event_type="BGP_SESSION_DOWN")
    classified = classify_event(evt)
    assert classified.category == EventCategory.ROUTING
    assert classified.severity == EventSeverity.CRITICAL

    # Test interface
    evt = NetworkEvent(event_type="link_flap")
    classified = classify_event(evt)
    assert classified.category == EventCategory.INTERFACE
    assert classified.severity == EventSeverity.ERROR

    # Test syslog
    evt = NetworkEvent(event_type="syslog_warning")
    classified = classify_event(evt)
    assert classified.category == EventCategory.SYSLOG
    assert classified.severity == EventSeverity.WARNING

    # Test unknown
    evt = NetworkEvent(event_type="something_random")
    classified = classify_event(evt)
    assert classified.category == EventCategory.UNKNOWN
    assert classified.severity == EventSeverity.INFO

    # Test no overwrite
    evt = NetworkEvent(event_type="bgp_down", category=EventCategory.SYSLOG)
    classified = classify_event(evt)
    assert classified.category == EventCategory.SYSLOG


def test_rca_correlator_basic(small_graph_data: dict[str, Any]) -> None:
    # Helper to convert small_graph_data to Topology
    edges = []
    for edge in small_graph_data.get("edges", []):
        edges.append(
            {
                "source": edge.get("src"),
                "target": edge.get("dst"),
            }
        )
    topo = Topology.from_dict({"nodes": small_graph_data.get("nodes", []), "edges": edges})

    correlator = RCACorrelator(topo)

    events = [
        NetworkEvent(
            event_id="e1", timestamp=10.0, node_id="A", event_type="link_down", peer_node="B"
        ),
        NetworkEvent(
            event_id="e2",
            timestamp=11.0,
            node_id="B",
            event_type="ospf_adjacency_loss",
            peer_node="A",
        ),
        NetworkEvent(event_id="e3", timestamp=12.0, node_id="C", event_type="syslog_error"),
    ]
    # Pre-classify
    for e in events:
        classify_event(e)

    result = correlator.diagnose(events)

    assert result.root_cause is not None
    # Verify that the correlator selects the highest-priority event (lowest number)
    # as the root cause, even if it occurs slightly later than lower-priority events.
    # e1: (10.0, 2 - INTERFACE)
    # e2: (11.0, 1 - ROUTING)
    # e3: (12.0, 3 - SYSLOG)
    # e2 has the highest priority (1).
    assert result.root_cause.event_id == "e2"
    assert result.total_events == 3
    assert "A" in result.affected_nodes
    assert "B" in result.affected_nodes
    assert "C" in result.affected_nodes

    # Test line 306: priority equal but timestamp earlier
    events2 = [
        NetworkEvent(event_id="e1", timestamp=10.0, node_id="A", event_type="link_down"),
        NetworkEvent(event_id="e2", timestamp=9.0, node_id="B", event_type="link_down"),
    ]
    for e in events2:
        classify_event(e)
    result2 = correlator.diagnose(events2)
    assert result2.root_cause.event_id == "e2"


def test_rca_correlator_no_events(small_graph_data: dict[str, Any]) -> None:
    topo = Topology.from_dict({"nodes": [], "edges": []})
    correlator = RCACorrelator(topo)
    result = correlator.diagnose([])
    assert result.root_cause is None
    assert result.total_events == 0
    assert result.root_cause_summary == "No events provided."


def test_rca_result_to_dict() -> None:
    evt = NetworkEvent(
        event_id="e1",
        node_id="A",
        event_type="link_down",
        category=EventCategory.INTERFACE,
        message="Link down message",
    )

    res = RCAResult(
        root_cause=evt,
        root_cause_summary="Summary",
        correlation_chain=[evt],
        affected_nodes={"A", "B"},
        affected_edges={("A", "B")},
        total_events=1,
    )
    d = res.to_dict()
    assert d["root_cause"]["event_id"] == "e1"
    assert d["affected_nodes"] == ["A", "B"]
    assert d["affected_edges"] == [["A", "B"]]
    assert d["total_events"] == 1


def test_rca_correlator_summary_with_message(small_graph_data: dict[str, Any]) -> None:
    topo = Topology.from_dict({"nodes": [], "edges": []})
    correlator = RCACorrelator(topo)
    evt = NetworkEvent(
        event_id="e1",
        node_id="A",
        event_type="link_down",
        category=EventCategory.INTERFACE,
        message="Critical link failure",
        peer_node="B",
    )
    result = correlator.diagnose([evt])
    assert "Detail: Critical link failure" in result.root_cause_summary
    assert "(peer: 'B')" in result.root_cause_summary
