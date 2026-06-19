"""Unit tests for the FailureInjector class."""

from __future__ import annotations

import pytest

from nroute.core.topology import Topology
from nroute.simulation.failure_injector import FailureInjector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_topology() -> Topology:
    """Build a minimal 3-node, 2-link topology for testing."""
    topo = Topology()
    topo.add_node("A", capacity=1000.0, utilization=0.0)
    topo.add_node("B", capacity=1000.0, utilization=0.0)
    topo.add_node("C", capacity=1000.0, utilization=0.0)
    topo.add_edge("A", "B", bandwidth=100.0, latency=5.0)
    topo.add_edge("B", "C", bandwidth=100.0, latency=10.0)
    return topo


# ---------------------------------------------------------------------------
# Scheduling tests
# ---------------------------------------------------------------------------


def test_schedule_link_failure() -> None:
    fi = FailureInjector()
    fi.schedule_link_failure("A", "B", tick=3)
    assert 3 in fi.events
    assert fi.events[3][0]["type"] == "link_failure"
    assert fi.events[3][0]["src"] == "A"
    assert fi.events[3][0]["dst"] == "B"


def test_schedule_node_failure() -> None:
    fi = FailureInjector()
    fi.schedule_node_failure("A", tick=5)
    assert 5 in fi.events
    assert fi.events[5][0]["type"] == "node_failure"
    assert fi.events[5][0]["node_id"] == "A"


def test_schedule_recovery() -> None:
    fi = FailureInjector()
    fi.schedule_recovery("A", "B", tick=7)
    assert fi.events[7][0]["type"] == "link_recovery"
    assert fi.events[7][0]["src"] == "A"


def test_schedule_node_recovery() -> None:
    fi = FailureInjector()
    fi.schedule_node_recovery("B", tick=8)
    assert fi.events[8][0]["type"] == "node_recovery"
    assert fi.events[8][0]["node_id"] == "B"


def test_schedule_latency_spike() -> None:
    fi = FailureInjector()
    fi.schedule_latency_spike("A", "B", tick=2, multiplier=3.0, duration_ticks=4)
    assert fi.events[2][0]["type"] == "latency_spike"
    assert fi.events[2][0]["multiplier"] == pytest.approx(3.0)
    assert fi.events[2][0]["duration"] == 4


def test_multiple_events_same_tick() -> None:
    fi = FailureInjector()
    fi.schedule_link_failure("A", "B", tick=1)
    fi.schedule_node_failure("C", tick=1)
    assert len(fi.events[1]) == 2


# ---------------------------------------------------------------------------
# apply() — link failure & recovery
# ---------------------------------------------------------------------------


def test_apply_link_failure_and_recovery() -> None:
    topo = _simple_topology()
    fi = FailureInjector()
    fi.schedule_link_failure("A", "B", tick=1)
    fi.apply(topo, current_tick=1)
    assert topo.get_edge("A", "B")["status"] == "down"

    fi.schedule_recovery("A", "B", tick=2)
    fi.apply(topo, current_tick=2)
    assert topo.get_edge("A", "B")["status"] == "up"


def test_apply_node_failure_and_recovery() -> None:
    topo = _simple_topology()
    fi = FailureInjector()
    fi.schedule_node_failure("A", tick=1)
    fi.apply(topo, current_tick=1)
    assert topo.get_node("A")["status"] == "down"

    fi.schedule_node_recovery("A", tick=2)
    fi.apply(topo, current_tick=2)
    assert topo.get_node("A")["status"] == "up"


# ---------------------------------------------------------------------------
# apply() — latency spike + auto-restore
# ---------------------------------------------------------------------------


def test_apply_latency_spike_then_restore() -> None:
    topo = _simple_topology()
    fi = FailureInjector()
    original_latency = topo.get_edge("A", "B")["latency"]

    fi.schedule_latency_spike("A", "B", tick=0, multiplier=4.0, duration_ticks=3)
    fi.apply(topo, current_tick=0)

    spiked_latency = topo.get_edge("A", "B")["latency"]
    assert spiked_latency == pytest.approx(original_latency * 4.0)
    # A restore_latency event should have been auto-scheduled at tick 3
    assert 3 in fi.events
    restore_events = [e for e in fi.events[3] if e["type"] == "restore_latency"]
    assert len(restore_events) == 1

    # Apply at tick 3 — latency should be restored
    fi.apply(topo, current_tick=3)
    restored_latency = topo.get_edge("A", "B")["latency"]
    assert restored_latency == pytest.approx(original_latency)


def test_apply_latency_spike_idempotent_original_store() -> None:
    """Second spike on same link before restore should not overwrite original."""
    topo = _simple_topology()
    fi = FailureInjector()
    original_latency = topo.get_edge("A", "B")["latency"]

    fi.schedule_latency_spike("A", "B", tick=0, multiplier=2.0, duration_ticks=5)
    fi.apply(topo, current_tick=0)
    first_spiked = topo.get_edge("A", "B")["latency"]

    # Apply a second spike — _original_latencies already has the key, so it
    # should NOT overwrite with the already-spiked value
    fi.schedule_latency_spike("A", "B", tick=1, multiplier=2.0, duration_ticks=5)
    fi.apply(topo, current_tick=1)

    # The stored original should still be the true original
    assert fi._original_latencies[("A", "B")] == pytest.approx(original_latency)
    assert first_spiked > original_latency  # confirm spike happened


# ---------------------------------------------------------------------------
# apply() — tick with no events is a no-op
# ---------------------------------------------------------------------------


def test_apply_no_events_noop() -> None:
    topo = _simple_topology()
    fi = FailureInjector()
    # Should not raise
    fi.apply(topo, current_tick=99)
    assert topo.get_edge("A", "B")["status"] == "up"
