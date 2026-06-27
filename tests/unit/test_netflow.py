"""Unit tests for the NetFlow ingestion module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pandas as pd
import pytest

from nroute.exceptions import IngestionError
from nroute.ingestion.netflow import NetFlowParser

if TYPE_CHECKING:
    from pathlib import Path


def test_netflow_parser_standard_headers(tmp_path: Path) -> None:
    """Test NetFlow parser with standard headers and valid data."""
    csv_file = tmp_path / "netflow.csv"
    df = pd.DataFrame(
        {
            "src_addr": ["10.0.0.1"],
            "dst_addr": ["10.0.0.2"],
            "bytes": [1000],
            "packets": [10],
            "protocol": ["TCP"],
            "timestamp": [100.0],
            "duration": [1.5],
        }
    )
    df.to_csv(csv_file, index=False)

    tm = NetFlowParser.parse(csv_file)
    assert len(tm.flows) == 1
    flow = tm.flows[0]
    assert flow.source == "10.0.0.1"
    assert flow.destination == "10.0.0.2"
    assert flow.bytes == 1000
    assert flow.packets == 10
    assert flow.protocol == "TCP"
    assert flow.timestamp == 100.0
    assert flow.duration == 1.5


def test_netflow_parser_varied_headers(tmp_path: Path) -> None:
    """Test NetFlow parser with various header aliases."""
    csv_file = tmp_path / "netflow_alt.csv"
    df = pd.DataFrame(
        {
            "IPv4_SRC_ADDR": ["192.168.1.1"],
            "ipv4_dst_addr": ["192.168.1.2"],
            "InOctets": [500],
            "InPkts": [5],
            "Proto": ["UDP"],
            "First": [200.0],
            "Last": [205.0],
        }
    )
    df.to_csv(csv_file, index=False)

    tm = NetFlowParser.parse(csv_file)
    assert len(tm.flows) == 1
    flow = tm.flows[0]
    assert flow.source == "192.168.1.1"
    assert flow.destination == "192.168.1.2"
    assert flow.bytes == 500
    assert flow.packets == 5
    assert flow.protocol == "UDP"
    assert flow.timestamp == 200.0
    assert flow.duration == 5.0


def test_netflow_parser_more_aliases(tmp_path: Path) -> None:
    """Test NetFlow parser with more header aliases to ensure coverage."""
    csv_file = tmp_path / "netflow_aliases.csv"
    df = pd.DataFrame(
        {
            "src": ["10.0.0.1"],
            "dst": ["10.0.0.2"],
            "d_octets": [1234],
            "d_pkts": [12],
            "pr": ["TCP"],
            "start_time": [300.0],
        }
    )
    df.to_csv(csv_file, index=False)

    tm = NetFlowParser.parse(csv_file)
    assert tm.flows[0].source == "10.0.0.1"
    assert tm.flows[0].bytes == 1234
    assert tm.flows[0].packets == 12
    assert tm.flows[0].protocol == "TCP"
    assert tm.flows[0].timestamp == 300.0


def test_netflow_parser_duration_last_switched(tmp_path: Path) -> None:
    """Test duration calculation using last_switched."""
    csv_file = tmp_path / "netflow_switched.csv"
    df = pd.DataFrame(
        {
            "src": ["1.1.1.1"],
            "dst": ["2.2.2.2"],
            "octets": [100],
            "pkts": [1],
            "pr": ["ICMP"],
            "first_switched": [500.0],
            "last_switched": [510.0],
        }
    )
    df.to_csv(csv_file, index=False)

    tm = NetFlowParser.parse(csv_file)
    assert tm.flows[0].duration == 10.0


def test_netflow_parser_duration_clipped(tmp_path: Path) -> None:
    """Test that negative duration is clipped to 0.0."""
    csv_file = tmp_path / "netflow_negative.csv"
    df = pd.DataFrame(
        {
            "source": ["A"],
            "destination": ["B"],
            "bytes": [100],
            "packets": [1],
            "protocol": ["TCP"],
            "timestamp": [100.0],
            "last": [90.0],
        }
    )
    df.to_csv(csv_file, index=False)

    tm = NetFlowParser.parse(csv_file)
    assert tm.flows[0].duration == 0.0


def test_netflow_parser_duration_missing(tmp_path: Path) -> None:
    """Test that duration defaults to 0.0 if no end time is provided."""
    csv_file = tmp_path / "netflow_no_end.csv"
    df = pd.DataFrame(
        {
            "source": ["A"],
            "destination": ["B"],
            "bytes": [100],
            "packets": [1],
            "protocol": ["TCP"],
            "timestamp": [100.0],
        }
    )
    df.to_csv(csv_file, index=False)

    tm = NetFlowParser.parse(csv_file)
    assert tm.flows[0].duration == 0.0


def test_netflow_parser_missing_file() -> None:
    """Test error when file is missing."""
    with pytest.raises(IngestionError, match="NetFlow CSV file not found"):
        NetFlowParser.parse("non_existent_file.csv")


def test_netflow_parser_invalid_csv(tmp_path: Path) -> None:
    """Test error when file is not a valid CSV."""
    invalid_file = tmp_path / "invalid.csv"
    with open(invalid_file, "w", encoding="utf-8") as f:
        f.write("this is not a csv\nwith,too,many,commas,on,one,line\nbut,not,on,another")

    # pandas might still read it, but let's try to trigger a read error if possible
    # Actually pd.read_csv is quite robust. Let's mock it to throw.
    with patch("pandas.read_csv", side_effect=Exception("Read error")), pytest.raises(
        IngestionError, match="Failed to read NetFlow CSV file"
    ):
        NetFlowParser.parse(invalid_file)


def test_netflow_parser_missing_required_columns(tmp_path: Path) -> None:
    """Test error when required columns are missing."""
    csv_file = tmp_path / "missing_cols.csv"
    # Missing 'protocol'
    df = pd.DataFrame(
        {
            "src": ["A"],
            "dst": ["B"],
            "bytes": [100],
            "packets": [1],
        }
    )
    df.to_csv(csv_file, index=False)

    with pytest.raises(IngestionError, match="missing required columns"):
        NetFlowParser.parse(csv_file)
