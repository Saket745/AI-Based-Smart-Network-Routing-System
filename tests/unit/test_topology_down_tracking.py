"""Tests for down tracking of nodes and edges in Topology."""

from __future__ import annotations

import pytest

from nroute.core.topology import Topology


def test_topology_down_tracking() -> None:
    """Verify that down nodes and edges are tracked accurately in O(1)."""
    topo = Topology()
    topo.add_node("A", status="up")
    topo.add_node("B", status="down")
    topo.add_node("C", status="up")

    assert topo.has_down_nodes is True
    assert topo._down_nodes == {"B"}

    topo.add_edge("A", "B", status="down")
    topo.add_edge("B", "C", status="up")

    assert topo.has_down_edges is True
    assert topo._down_edges == {("A", "B")}

    # Toggle node down (this should mark incident links down too)
    topo.set_node_down("C")
    assert topo._down_nodes == {"B", "C"}
    # Incident edges to C: ("B", "C") should now be down
    assert ("B", "C") in topo._down_edges

    # Toggle node back up
    topo.set_node_up("C")
    assert topo._down_nodes == {"B"}
    # ("B", "C") should be back up
    assert ("B", "C") not in topo._down_edges

    # Copy topology
    copied = topo.copy()
    assert copied.has_down_nodes is True
    assert copied._down_nodes == {"B"}

    # Remove node
    topo.remove_node("B")
    assert topo.has_down_nodes is False
    assert topo._down_nodes == set()
