"""Unit tests for the traffic models."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from nroute.core.traffic import FlowRecord, TrafficMatrix
from nroute.exceptions import IngestionError


def test_flow_record_init() -> None:
    """Test initializing a FlowRecord."""
    flow = FlowRecord(
        source="A",
        destination="B",
        bytes=1000,
        packets=10,
        duration=1.5,
        protocol="TCP",
        timestamp=100.0,
    )
    assert flow.source == "A"
    assert flow.destination == "B"
    assert flow.bytes == 1000
    assert flow.packets == 10
    assert flow.duration == 1.5
    assert flow.protocol == "TCP"
    assert flow.timestamp == 100.0


def test_traffic_matrix_to_from_dataframe() -> None:
    """Test converting TrafficMatrix to and from a pandas DataFrame."""
    flows = [
        FlowRecord(
            source="A",
            destination="B",
            bytes=100,
            packets=1,
            duration=0.1,
            protocol="UDP",
            timestamp=0.0,
        ),
        FlowRecord(
            source="B",
            destination="C",
            bytes=200,
            packets=2,
            duration=0.2,
            protocol="TCP",
            timestamp=1.0,
        ),
    ]
    tm = TrafficMatrix(flows=flows)

    df = tm.to_dataframe()
    assert len(df) == 2
    assert list(df.columns) == [
        "source",
        "destination",
        "bytes",
        "packets",
        "duration",
        "protocol",
        "timestamp",
    ]

    tm2 = TrafficMatrix.from_dataframe(df)
    assert len(tm2.flows) == 2
    assert tm2.flows[0].source == "A"
    assert tm2.flows[1].protocol == "TCP"


def test_traffic_matrix_from_dataframe_missing_cols() -> None:
    """Test error when creating TrafficMatrix from incomplete DataFrame."""
    df = pd.DataFrame({"source": ["A"], "destination": ["B"]})
    with pytest.raises(IngestionError, match="missing required flow columns"):
        TrafficMatrix.from_dataframe(df)


def test_traffic_matrix_from_csv(tmp_path: Any) -> None:
    """Test loading TrafficMatrix from a CSV file."""
    csv_path = tmp_path / "traffic.csv"
    df = pd.DataFrame(
        {
            "source": ["A", "B"],
            "destination": ["B", "C"],
            "bytes": [100, 200],
            "packets": [1, 2],
            "duration": [0.1, 0.2],
            "protocol": ["UDP", "TCP"],
            "timestamp": [0.0, 1.0],
        }
    )
    df.to_csv(csv_path, index=False)

    tm = TrafficMatrix.from_csv(csv_path)
    assert len(tm.flows) == 2
    assert tm.flows[0].source == "A"


def test_traffic_matrix_from_csv_missing_file() -> None:
    """Test error when loading from non-existent CSV."""
    with pytest.raises(IngestionError, match="Traffic CSV file does not exist"):
        TrafficMatrix.from_csv("/nonexistent/file.csv")


def test_traffic_matrix_filter_by_time() -> None:
    """Test filtering flows by timestamp."""
    flows = [
        FlowRecord(
            source="A",
            destination="B",
            bytes=100,
            packets=1,
            duration=0.1,
            protocol="UDP",
            timestamp=10.0,
        ),
        FlowRecord(
            source="B",
            destination="C",
            bytes=200,
            packets=2,
            duration=0.2,
            protocol="TCP",
            timestamp=20.0,
        ),
        FlowRecord(
            source="C",
            destination="A",
            bytes=300,
            packets=3,
            duration=0.3,
            protocol="ICMP",
            timestamp=30.0,
        ),
    ]
    tm = TrafficMatrix(flows=flows)

    filtered = tm.filter_by_time(15.0, 25.0)
    assert len(filtered.flows) == 1
    assert filtered.flows[0].timestamp == 20.0


def test_traffic_matrix_summary() -> None:
    """Test traffic matrix summary string generation."""
    tm_empty = TrafficMatrix(flows=[])
    assert "Empty Traffic Matrix" in tm_empty.summary()

    flows = [
        FlowRecord(
            source="A",
            destination="B",
            bytes=1000,
            packets=10,
            duration=0.1,
            protocol="TCP",
            timestamp=0.0,
        ),
        FlowRecord(
            source="B",
            destination="A",
            bytes=2000,
            packets=20,
            duration=0.2,
            protocol="TCP",
            timestamp=0.1,
        ),
    ]
    tm = TrafficMatrix(flows=flows)
    summary = tm.summary()
    assert "Total Flows: 2" in summary
    assert "3,000 bytes" in summary
    assert "30 packets" in summary
    assert "TCP: 2" in summary
