"""Unit tests for the live terminal visualization console."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from rich.layout import Layout

from nroute.core.metrics import MetricsCollectionResult, SimulationMetrics
from nroute.core.topology import Topology
from nroute.exceptions import TopologyError
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

    # Test flow completion logging
    mock_flow = MagicMock()
    mock_flow.source = "A"
    mock_flow.destination = "B"
    mock_flow.bytes = 1000
    mock_flow.duration = 0.005
    engine.last_tick_completed_flows = [mock_flow]

    # Test flow drop logging
    engine.last_tick_dropped_flows = [(mock_flow, "TTL Exceeded")]

    # Test reroute logging
    engine.last_tick_reroute_count = 1

    console_viz.update_events(tick=2)
    assert any("Flow A ➔ B completed" in event for event in console_viz.event_log)
    assert any("Flow A ➔ B DROPPED" in event for event in console_viz.event_log)
    assert any("Mid-flow rerouting triggered" in event for event in console_viz.event_log)

    # Test event log rotation
    for i in range(100):
        console_viz.log_event(f"Event {i}")
    assert len(console_viz.event_log) == 50


def test_live_console_error_handling() -> None:
    """Verify LiveSimulationConsole handles and logs topology access errors."""
    topo = Topology()
    topo.add_node("A", type="router")
    topo.add_node("B", type="router")
    topo.add_edge("A", "B", bandwidth=1000, latency=5)

    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1)
    engine = SimulationEngine(topo, router, traffic)

    console_viz = LiveSimulationConsole(engine, duration_ticks=5, delay=0.0)

    # Mock get_edge and get_node to raise TopologyError
    with (
        patch.object(engine.topology, "get_edge", side_effect=TopologyError("Edge error")),
        patch.object(engine.topology, "get_node", side_effect=TopologyError("Node error")),
        patch("nroute.visualization.live_console.logger") as mock_logger,
    ):
        console_viz.update_events(tick=0)
        # Verify errors were logged
        assert mock_logger.error.called

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


def test_live_console_status_transitions() -> None:
    """Verify that the console tracking status transitions through Initializing, Running, and Completed states."""
    topo = Topology()
    topo.add_node("A", type="router")
    topo.add_node("B", type="router")
    topo.add_edge("A", "B", bandwidth=1000, latency=5)

    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1)
    engine = SimulationEngine(topo, router, traffic)

    console_viz = LiveSimulationConsole(engine, duration_ticks=2, delay=0.0)

    # 1. Check initial state
    assert console_viz.status == "Initializing"
    header_init = console_viz._build_header(None, None, "DijkstraRouter")
    assert "Initializing" in header_init.renderable.plain

    # Mock engine run to verify completion status
    with patch.object(engine, "run", return_value=MagicMock()):
        console_viz.run()
        assert console_viz.status == "Completed"


def test_live_console_ctrl_c_hint() -> None:
    """Verify the header contains the Ctrl+C keyboard hint."""
    topo = Topology()
    topo.add_node("A", type="router")
    topo.add_node("B", type="router")
    topo.add_edge("A", "B", bandwidth=1000, latency=5)

    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1)
    engine = SimulationEngine(topo, router, traffic)

    console_viz = LiveSimulationConsole(engine, duration_ticks=5, delay=0.0)
    header_panel = console_viz._build_header(0, None, "DijkstraRouter")
    header_text = header_panel.renderable.plain
    assert "Ctrl+C" in header_text
    assert "Quit" in header_text


def test_live_console_keyboard_interrupt_handling() -> None:
    """Verify KeyboardInterrupt produces a clean MetricsCollectionResult preserving collected metrics."""
    topo = Topology()
    topo.add_node("A", type="router")
    topo.add_node("B", type="router")
    topo.add_edge("A", "B", bandwidth=1000, latency=5)

    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1)
    engine = SimulationEngine(topo, router, traffic)

    console_viz = LiveSimulationConsole(engine, duration_ticks=10, delay=0.0)

    # Simulate already collected metrics
    mock_metric = SimulationMetrics(
        tick=0,
        timestamp=0.0,
        throughput=100.0,
        avg_latency=5.0,
        packet_loss_rate=0.0,
        avg_utilization=0.1,
        reroute_count=0,
        active_flows=1,
    )
    engine.collector.results.append(mock_metric)

    # Mock engine.run to raise KeyboardInterrupt
    with (
        patch.object(engine, "run", side_effect=KeyboardInterrupt),
        patch("nroute.visualization.live_console.Live"),
    ):
        result = console_viz.run()
        assert isinstance(result, MetricsCollectionResult)
        assert len(result.results) == 1
        assert result.results[0].throughput == 100.0
        assert console_viz.status == "Completed"


def test_live_console_normal_completion_preserved() -> None:
    """Verify normal completion behavior remains unchanged and returns full results."""
    topo = Topology()
    topo.add_node("A", type="router")
    topo.add_node("B", type="router")
    topo.add_edge("A", "B", bandwidth=1000, latency=5)

    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1)
    engine = SimulationEngine(topo, router, traffic)

    console_viz = LiveSimulationConsole(engine, duration_ticks=2, delay=0.0)

    mock_metrics = [
        SimulationMetrics(
            tick=0,
            timestamp=0.0,
            throughput=100.0,
            avg_latency=5.0,
            packet_loss_rate=0.0,
            avg_utilization=0.1,
            reroute_count=0,
            active_flows=1,
        ),
        SimulationMetrics(
            tick=1,
            timestamp=1.0,
            throughput=120.0,
            avg_latency=4.8,
            packet_loss_rate=0.0,
            avg_utilization=0.15,
            reroute_count=0,
            active_flows=1,
        ),
    ]
    engine.collector.results.extend(mock_metrics)
    expected_result = MetricsCollectionResult(results=mock_metrics)

    with (
        patch.object(engine, "run", return_value=expected_result) as mock_run,
        patch("nroute.visualization.live_console.Live"),
    ):
        result = console_viz.run()
        mock_run.assert_called_once()
        assert result == expected_result
        assert console_viz.status == "Completed"



def test_live_console_progress_bar_rendering() -> None:
    """Verify that the compact progress bar renders correctly in the console header."""
    topo = Topology()
    topo.add_node("A", type="router")
    topo.add_node("B", type="router")
    topo.add_edge("A", "B", bandwidth=1000, latency=5)

    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=1)
    engine = SimulationEngine(topo, router, traffic)

    # 1. Start simulation, duration = 10. At tick 0, progress is 1/10 = 10%
    console_viz = LiveSimulationConsole(engine, duration_ticks=10, delay=0.0)
    header_panel = console_viz._build_header(0, None, "DijkstraRouter")
    header_text = header_panel.renderable.plain
    # Expect bar to be [█░░░░░░░░░] 10%
    assert "[█░░░░░░░░░] 10%" in header_text

    # 2. At tick 4, progress is 5/10 = 50%
    header_panel = console_viz._build_header(4, None, "DijkstraRouter")
    header_text = header_panel.renderable.plain
    # Expect bar to be [█████░░░░░] 50%
    assert "[█████░░░░░] 50%" in header_text

    # 3. At tick 9, progress is 10/10 = 100%
    header_panel = console_viz._build_header(9, None, "DijkstraRouter")
    header_text = header_panel.renderable.plain
    # Expect bar to be [██████████] 100%
    assert "[██████████] 100%" in header_text
