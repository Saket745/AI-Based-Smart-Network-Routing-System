"""RCA loader benchmarks using pytest-benchmark."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from nroute.simulation.rca import load_events


@pytest.fixture
def temp_events_files() -> tuple[Path, Path]:
    """Create temporary YAML and JSON files with events."""
    events_data = [
        {
            "event_id": f"evt_{i}",
            "timestamp": float(i),
            "node_id": f"R{i % 10}",
            "event_type": "link_down" if i % 2 == 0 else "bgp_session_down",
            "message": f"Event detail {i}",
        }
        for i in range(100)
    ]

    tmp_dir = Path(tempfile.mkdtemp())
    json_path = tmp_dir / "events.json"
    yaml_path = tmp_dir / "events.yaml"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(events_data, f)

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(events_data, f)

    return json_path, yaml_path

@pytest.mark.benchmark
def test_bench_load_events_json(temp_events_files: tuple[Path, Path], benchmark: Any) -> None:
    """Benchmark loading events from JSON multiple times."""
    json_path, _ = temp_events_files

    def run_load() -> None:
        for _ in range(50):
            load_events(json_path)

    benchmark(run_load)

@pytest.mark.benchmark
def test_bench_load_events_yaml(temp_events_files: tuple[Path, Path], benchmark: Any) -> None:
    """Benchmark loading events from YAML multiple times."""
    _, yaml_path = temp_events_files

    def run_load() -> None:
        for _ in range(50):
            load_events(yaml_path)

    benchmark(run_load)
