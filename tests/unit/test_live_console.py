"""Unit tests for the live terminal visualization console."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from rich.layout import Layout

from nroute.core.metrics import SimulationMetrics
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
        plain_text = "".join(s.plain for s in segments)
        assert "RedPlot" in plain_text


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
    # Toggling node down on the engine's copied topology directly
    engine.topology.set_node_down("A")
    console_viz.update_events(tick=0)
    assert any("Node A went DOWN" in event for event in console_viz.event_log)

    # Toggling node back up on the engine's copied topology directly
    engine.topology.set_node_up("A")
    console_viz.update_events(tick=1)
    assert any("Node A recovered (UP)" in event for event in console_viz.event_log)


def test_live_console_helpers() -> None:
    """Test individual helper methods of LiveSimulationConsole."""
    topo = Topology()
    topo.add_node("A", type="router")
    topo.add_node("B", type="router")
    topo.add_edge("A", "B", bandwidth=1000, latency=5)

    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1)
    engine = SimulationEngine(topo, router, traffic)

    console_viz = LiveSimulationConsole(engine, duration_ticks=5, delay=0.0)

    metric = SimulationMetrics(
        tick=0,
        timestamp=0.0,
        throughput=150.0,
        avg_latency=12.5,
        packet_loss_rate=0.0,
        avg_utilization=0.3,
        reroute_count=0,
        active_flows=2,
    )

    # Test _update_history
    console_viz._update_history(0, metric)
    assert console_viz.ticks_history == [0]
    assert console_viz.throughput_history == [150.0]
    assert console_viz.latency_history == [12.5]

    # Test _build_header
    header_panel = console_viz._build_header(0, metric, "DijkstraRouter")
    assert header_panel is not None

    # Test _build_link_status_table
    table = console_viz._build_link_status_table(engine)
    assert table is not None
    assert table.row_count == 1

    # Test _update_layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=8),
    )
    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1),
    )
    layout["right"].split_column(
        Layout(name="throughput_plot", ratio=1),
        Layout(name="latency_plot", ratio=1),
    )

    console_viz._update_layout(layout, 0, metric, "DijkstraRouter", engine)
    assert layout["header"] is not None
