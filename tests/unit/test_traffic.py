"""Unit tests for traffic data models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import pytest
from pydantic import ValidationError

from nroute.core.traffic import FlowRecord, TrafficMatrix
from nroute.exceptions import IngestionError

if TYPE_CHECKING:
    from pathlib import Path


def test_flow_record_validation() -> None:
    """Test FlowRecord pydantic validation."""
    # Valid record
    flow = FlowRecord(
        source="node1",
        destination="node2",
        bytes=100,
        packets=10,
        duration=1.5,
        protocol="TCP",
        timestamp=100.0,
    )
    assert flow.source == "node1"
    assert flow.bytes == 100

    # Negative values should fail
    with pytest.raises(ValidationError):
        FlowRecord(
            source="node1",
            destination="node2",
            bytes=-1,
            packets=10,
            duration=1.5,
            protocol="TCP",
            timestamp=100.0,
        )

    with pytest.raises(ValidationError):
        FlowRecord(
            source="node1",
            destination="node2",
            bytes=100,
            packets=-10,
            duration=1.5,
            protocol="TCP",
            timestamp=100.0,
        )

    with pytest.raises(ValidationError):
        FlowRecord(
            source="node1",
            destination="node2",
            bytes=100,
            packets=10,
            duration=-1.5,
            protocol="TCP",
            timestamp=100.0,
        )


def test_traffic_matrix_to_dataframe() -> None:
    """Test converting TrafficMatrix to pandas DataFrame."""
    # Empty matrix
    tm_empty = TrafficMatrix()
    df_empty = tm_empty.to_dataframe()
    assert isinstance(df_empty, pd.DataFrame)
    assert len(df_empty) == 0
    assert "source" in df_empty.columns

    # Matrix with flows
    flow = FlowRecord(
        source="A",
        destination="B",
        bytes=500,
        packets=5,
        duration=0.1,
        protocol="UDP",
        timestamp=0.0,
    )
    tm = TrafficMatrix(flows=[flow])
    df = tm.to_dataframe()
    assert len(df) == 1
    assert df.iloc[0]["source"] == "A"
    assert df.iloc[0]["bytes"] == 500


def test_traffic_matrix_from_dataframe() -> None:
    """Test creating TrafficMatrix from pandas DataFrame."""
    data = {
        "source": ["A", "B"],
        "destination": ["B", "C"],
        "bytes": [100, 200],
        "packets": [10, 20],
        "duration": [1.0, 2.0],
        "protocol": ["TCP", "UDP"],
        "timestamp": [0.0, 1.0],
    }
    df = pd.DataFrame(data)
    tm = TrafficMatrix.from_dataframe(df)
    assert len(tm.flows) == 2
    assert tm.flows[0].source == "A"
    assert tm.flows[1].bytes == 200

    # Missing columns
    df_missing = df.drop(columns=["bytes"])
    with pytest.raises(IngestionError, match="missing required flow columns"):
        TrafficMatrix.from_dataframe(df_missing)

    # Invalid data types / values
    df_invalid = df.copy()
    df_invalid.at[0, "bytes"] = -100  # Should fail FlowRecord validation
    with pytest.raises(IngestionError, match="Failed to parse flow record"):
        TrafficMatrix.from_dataframe(df_invalid)


def test_traffic_matrix_from_csv(tmp_path: Path) -> None:
    """Test loading TrafficMatrix from CSV file."""
    csv_file = tmp_path / "traffic.csv"
    data = (
        "source,destination,bytes,packets,duration,protocol,timestamp\n"
        "A,B,100,10,1.0,TCP,0.0\n"
        "B,C,200,20,2.0,UDP,1.0"
    )
    csv_file.write_text(data)

    tm = TrafficMatrix.from_csv(csv_file)
    assert len(tm.flows) == 2
    assert tm.flows[0].source == "A"

    # Non-existent file
    with pytest.raises(IngestionError, match="does not exist"):
        TrafficMatrix.from_csv(tmp_path / "non_existent.csv")

    # Corrupt CSV
    corrupt_file = tmp_path / "corrupt.csv"
    corrupt_file.write_text("invalid,csv,data")
    with pytest.raises(IngestionError):
        TrafficMatrix.from_csv(corrupt_file)


def test_traffic_matrix_filter_by_time() -> None:
    """Test filtering flows by timestamp."""
    flows = [
        FlowRecord(
            source="A",
            destination="B",
            bytes=100,
            packets=10,
            duration=1.0,
            protocol="TCP",
            timestamp=10.0,
        ),
        FlowRecord(
            source="B",
            destination="C",
            bytes=200,
            packets=20,
            duration=2.0,
            protocol="UDP",
            timestamp=20.0,
        ),
        FlowRecord(
            source="C",
            destination="D",
            bytes=300,
            packets=30,
            duration=3.0,
            protocol="ICMP",
            timestamp=30.0,
        ),
    ]
    tm = TrafficMatrix(flows=flows)

    # Test inclusive bounds
    filtered = tm.filter_by_time(10.0, 20.0)
    assert len(filtered.flows) == 2
    assert {f.timestamp for f in filtered.flows} == {10.0, 20.0}

    filtered = tm.filter_by_time(15.0, 25.0)
    assert len(filtered.flows) == 1
    assert filtered.flows[0].timestamp == 20.0

    filtered_none = tm.filter_by_time(40.0, 50.0)
    assert len(filtered_none.flows) == 0


def test_traffic_matrix_summary() -> None:
    """Test the summary string generation."""
    tm_empty = TrafficMatrix()
    assert "Empty Traffic Matrix" in tm_empty.summary()

    flow = FlowRecord(
        source="A",
        destination="B",
        bytes=1000,
        packets=10,
        duration=1.0,
        protocol="TCP",
        timestamp=0.0,
    )
    tm = TrafficMatrix(flows=[flow, flow])
    summary = tm.summary()
    assert "Total Flows: 2" in summary
    assert "Total volume: 2,000 bytes (20 packets)" in summary
    assert "Protocols: TCP: 2" in summary
