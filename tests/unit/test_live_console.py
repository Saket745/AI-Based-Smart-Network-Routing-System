"""Unit tests for the live console visualizer."""

from __future__ import annotations

from unittest.mock import MagicMock

from rich.layout import Layout
from rich.panel import Panel

from nroute.core.metrics import SimulationMetrics
from nroute.core.topology import Topology
from nroute.routing import DijkstraRouter
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator
from nroute.visualization.live_console import LiveSimulationConsole, PlotextRenderable


def create_test_engine() -> SimulationEngine:
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_node("C")
    topo.add_edge("A", "B", bandwidth=1000.0, latency=5.0, utilization=0.2)
    topo.add_edge("B", "C", bandwidth=1000.0, latency=5.0, utilization=0.9)
    router = DijkstraRouter()
    traffic = TrafficGenerator(model="uniform", n_flows_per_tick=5)
    return SimulationEngine(topology=topo, router=router, traffic_generator=traffic)


def test_live_console_init() -> None:
    engine = create_test_engine()
    console = LiveSimulationConsole(engine=engine, duration_ticks=10, delay=0.0)
    assert console.duration_ticks == 10
    assert console.delay == 0.0
    assert console.event_log == []


def test_log_event() -> None:
    engine = create_test_engine()
    console = LiveSimulationConsole(engine=engine, duration_ticks=10)
    console.log_event("Test Event")
    assert len(console.event_log) == 1
    assert "Test Event" in console.event_log[0]

    # Test event log cap at 50
    for i in range(60):
        console.log_event(f"Event {i}")
    assert len(console.event_log) == 50
    assert "Event 59" in console.event_log[-1]


def test_update_events_link_down_up() -> None:
    engine = create_test_engine()
    console = LiveSimulationConsole(engine=engine, duration_ticks=10)

    # First update: links are up
    console.update_events(0)
    assert len(console.event_log) == 0

    # Bring link A -> B down
    engine.topology.set_link_down("A", "B")
    console.update_events(1)
    assert any("Link A ➔ B went DOWN" in log for log in console.event_log)

    # Bring link A -> B up
    engine.topology.set_link_up("A", "B")
    console.update_events(2)
    assert any("Link A ➔ B recovered" in log for log in console.event_log)


def test_update_events_node_down_up() -> None:
    engine = create_test_engine()
    console = LiveSimulationConsole(engine=engine, duration_ticks=10)

    # Node A down
    engine.topology.set_node_down("A")
    console.update_events(0)
    assert any("Node A went DOWN" in log for log in console.event_log)

    # Node A up
    engine.topology.set_node_up("A")
    console.update_events(1)
    assert any("Node A recovered" in log for log in console.event_log)


def test_plotext_renderable() -> None:
    mock_plot = MagicMock()
    renderable = PlotextRenderable(mock_plot)

    console = MagicMock()
    options = MagicMock()
    options.max_width = 80
    options.height = 20

    list(renderable.__rich_console__(console, options))
    assert mock_plot.called


def test_helper_update_history() -> None:
    engine = create_test_engine()
    console = LiveSimulationConsole(engine=engine, duration_ticks=10)
    metric = SimulationMetrics(
        tick=0,
        timestamp=0.0,
        throughput=100.0,
        avg_latency=12.5,
        packet_loss_rate=0.0,
        avg_utilization=0.5,
        reroute_count=0,
        active_flows=2,
    )
    console._update_history(0, metric)
    assert console.ticks_history == [0]
    assert console.throughput_history == [100.0]
    assert console.latency_history == [12.5]


def test_helper_build_header() -> None:
    engine = create_test_engine()
    console = LiveSimulationConsole(engine=engine, duration_ticks=10)
    metric = SimulationMetrics(
        tick=0,
        timestamp=0.0,
        throughput=100.0,
        avg_latency=12.5,
        packet_loss_rate=0.0,
        avg_utilization=0.5,
        reroute_count=0,
        active_flows=5,
    )
    panel = console._build_header(0, metric, "DijkstraRouter")
    assert isinstance(panel, Panel)
    assert "[Press Ctrl+C to Quit]" in panel.renderable.plain


def test_helper_build_link_status_table() -> None:
    engine = create_test_engine()
    console = LiveSimulationConsole(engine=engine, duration_ticks=10)
    table = console._build_link_status_table(engine)
    assert table.title == "Link Status & Utilization"


def test_helper_update_layout() -> None:
    engine = create_test_engine()
    console = LiveSimulationConsole(engine=engine, duration_ticks=10)
    layout = Layout()
    layout.split_column(
        Layout(name="header"),
        Layout(name="main"),
        Layout(name="footer"),
    )
    layout["main"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    layout["right"].split_column(
        Layout(name="throughput_plot"),
        Layout(name="latency_plot"),
    )
    metric = SimulationMetrics(
        tick=0,
        timestamp=0.0,
        throughput=100.0,
        avg_latency=12.5,
        packet_loss_rate=0.0,
        avg_utilization=0.5,
        reroute_count=0,
        active_flows=2,
    )
    console.log_event("Event 1")
    console._update_layout(layout, 0, metric, "DijkstraRouter", engine)
