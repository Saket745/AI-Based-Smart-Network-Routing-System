"""Unit tests for the live terminal visualization console."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from nroute.core.topology import Topology
from nroute.routing.dijkstra import DijkstraRouter
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator
from nroute.visualization.live_console import LiveSimulationConsole, PlotextRenderable


def test_plotext_renderable() -> None:
    """Verify PlotextRenderable wraps plotext plots and decodes ANSI properly."""

    def plot_func(plt: Any) -> None:
        plt.plot([1, 2], [3, 4])

    renderable = PlotextRenderable(plot_func)
    options = MagicMock()
    options.max_width = 80
    options.height = 10

    with patch("plotext.build", return_value="\x1b[31mRedPlot\x1b[0m") as mock_build:
        segments = list(renderable.__rich_console__(MagicMock(), options))
        mock_build.assert_called_once()
        assert len(segments) > 0
        # Check that ANSI colors were decoded
        assert any(getattr(s, "text", "") == "RedPlot" for s in segments)


def test_live_console_basic_logging() -> None:
    """Verify LiveSimulationConsole logs events and tracks topology status changes."""
    topo = Topology()
    topo.add_node("A", type="router")
    topo.add_node("B", type="router")
    topo.add_edge("A", "B", bandwidth=1000, latency=5)

    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1)
    engine = SimulationEngine(topo, router, traffic)

    console_viz = LiveSimulationConsole(engine, duration_ticks=5, delay=0.0)

    # Test custom event logging
    console_viz.log_event("Initialize Simulation Run")
    assert len(console_viz.event_log) == 1
    assert "Initialize Simulation Run" in console_viz.event_log[0]

    # Test node down/up detection
    # Toggling node down
    topo.set_node_down("A")
    console_viz.update_events(tick=0)
    assert any("Node A went DOWN" in event for event in console_viz.event_log)

    # Toggling node back up
    topo.set_node_up("A")
    console_viz.update_events(tick=1)
    assert any("Node A recovered (UP)" in event for event in console_viz.event_log)
