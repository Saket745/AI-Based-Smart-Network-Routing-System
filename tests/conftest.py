"""Shared test fixtures for nroute test suite."""

from __future__ import annotations

import sys
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def cli_modules_and_commands() -> None:
    """Copy module attributes to Click Command/Group objects for CLI modules on Python < 3.12."""
    if sys.version_info < (3, 12):
        from nroute.cli import (
            detect_cmd,
            predict_cmd,
            route_cmd,
            simulate_cmd,
            topology_cmd,
        )

        cli_modules = [
            (detect_cmd, detect_cmd.detect_cmd),
            (predict_cmd, predict_cmd.predict_cmd),
            (route_cmd, route_cmd.route_cmd),
            (simulate_cmd, simulate_cmd.simulate_cmd),
            (topology_cmd, topology_cmd.topology_cmd),
        ]

        for mod, cmd in cli_modules:
            for attr in dir(mod):
                if not hasattr(cmd, attr):
                    setattr(cmd, attr, getattr(mod, attr))


@pytest.fixture
def small_graph_data() -> dict[str, Any]:
    """A small 5-node, 7-edge test graph with known weights.

    Topology:
        A --10ms--> B --5ms--> D
        |           |          ^
        15ms       8ms       3ms
        |           |          |
        v           v          |
        C --7ms---> E ---------+

    Nodes: A, B, C, D, E
    Edges (directed): A→B(10), A→C(15), B→D(5), B→E(8), C→E(7), E→D(3), D→A(20)

    Shortest path A→D:
        A → B → D (total: 15ms)
    Alternative:
        A → C → E → D (total: 25ms)
        A → B → E → D (total: 21ms)
    """
    return {
        "nodes": [
            {"id": "A", "type": "router", "capacity": 1000.0, "status": "up"},
            {"id": "B", "type": "router", "capacity": 1000.0, "status": "up"},
            {"id": "C", "type": "switch", "capacity": 500.0, "status": "up"},
            {"id": "D", "type": "router", "capacity": 1000.0, "status": "up"},
            {"id": "E", "type": "switch", "capacity": 500.0, "status": "up"},
        ],
        "edges": [
            {
                "src": "A",
                "dst": "B",
                "bandwidth": 1000.0,
                "latency": 10.0,
                "jitter": 0.5,
                "packet_loss": 0.0,
                "utilization": 0.0,
                "status": "up",
            },
            {
                "src": "A",
                "dst": "C",
                "bandwidth": 500.0,
                "latency": 15.0,
                "jitter": 1.0,
                "packet_loss": 0.0,
                "utilization": 0.0,
                "status": "up",
            },
            {
                "src": "B",
                "dst": "D",
                "bandwidth": 1000.0,
                "latency": 5.0,
                "jitter": 0.2,
                "packet_loss": 0.0,
                "utilization": 0.0,
                "status": "up",
            },
            {
                "src": "B",
                "dst": "E",
                "bandwidth": 800.0,
                "latency": 8.0,
                "jitter": 0.3,
                "packet_loss": 0.0,
                "utilization": 0.0,
                "status": "up",
            },
            {
                "src": "C",
                "dst": "E",
                "bandwidth": 500.0,
                "latency": 7.0,
                "jitter": 0.5,
                "packet_loss": 0.0,
                "utilization": 0.0,
                "status": "up",
            },
            {
                "src": "E",
                "dst": "D",
                "bandwidth": 800.0,
                "latency": 3.0,
                "jitter": 0.1,
                "packet_loss": 0.0,
                "utilization": 0.0,
                "status": "up",
            },
            {
                "src": "D",
                "dst": "A",
                "bandwidth": 1000.0,
                "latency": 20.0,
                "jitter": 1.0,
                "packet_loss": 0.0,
                "utilization": 0.0,
                "status": "up",
            },
        ],
    }


@pytest.fixture
def tmp_output_dir(tmp_path: Any) -> Any:
    """Provide a clean temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture(autouse=True)
def restore_cli_submodules() -> None:
    """Ensure nroute.cli.<cmd_name> attributes on nroute.cli point to modules rather than Click Group objects for unittest.mock.patch on Python 3.10."""
    import importlib
    import sys

    cli_modules = [
        "nroute.cli.topology_cmd",
        "nroute.cli.route_cmd",
        "nroute.cli.simulate_cmd",
        "nroute.cli.predict_cmd",
        "nroute.cli.detect_cmd",
        "nroute.cli.twin_cmd",
        "nroute.cli.export_cmd",
        "nroute.cli.api_cmd",
        "nroute.cli.configs_cmd",
        "nroute.cli.train_cmd",
    ]
    if "nroute.cli" in sys.modules:
        cli_pkg = sys.modules["nroute.cli"]
        for mod_name in cli_modules:
            try:
                mod = importlib.import_module(mod_name)
                attr_name = mod_name.split(".")[-1]
                setattr(cli_pkg, attr_name, mod)
            except Exception:
                pass
