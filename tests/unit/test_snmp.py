"""Unit tests for the SNMP Ingestion Parser."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from nroute.exceptions import IngestionError
from nroute.ingestion.snmp import SNMPParser

if TYPE_CHECKING:
    from pathlib import Path


def test_snmp_parser_csv_standard(tmp_path: Path) -> None:
    """Test standard SNMP counter CSV ingestion."""
    csv_file = tmp_path / "snmp.csv"
    df = pd.DataFrame(
        {
            "interface_id": ["A->B", "B-to-C", "C:D"],
            "speed": [10000000, 100000, 100],  # bps
            "in_octets": [125000, 5000, 0],
            "out_octets": [125000, 5000, 0],
            "oper_status": ["up", "testing", "2"],  # 2 means down in SNMP status
        }
    )
    df.to_csv(csv_file, index=False)

    topo = SNMPParser.parse(csv_file)
    assert topo.node_count == 4
    assert topo.edge_count == 3

    # Speed conversions: 10,000,000 bps = 10 Mbps
    assert topo.get_edge("A", "B")["bandwidth"] == 10.0
    assert topo.get_edge("B", "C")["bandwidth"] == 0.1
    # Status conversions
    assert topo.get_edge("A", "B")["status"] == "up"
    assert topo.get_edge("B", "C")["status"] == "degraded"
    assert topo.get_edge("C", "D")["status"] == "down"


def test_snmp_parser_csv_alternative_keys(tmp_path: Path) -> None:
    """Test SNMP parser with alternative key names (ifspeed, ifoperstatus, etc)."""
    csv_file = tmp_path / "snmp_alt.csv"
    df = pd.DataFrame(
        {
            "INTERFACE_ID": ["X->Y"],
            "ifSpeed": [1000000],
            "ifInCheck": [1000],
            "ifOutCheck": [2000],
            "ifOperStatus": ["up"],
        }
    )
    df.to_csv(csv_file, index=False)

    topo = SNMPParser.parse(csv_file)
    assert topo.edge_count == 1
    edge = topo.get_edge("X", "Y")
    assert edge["bandwidth"] == 1.0
    assert edge["in_octets"] == 1000
    assert edge["out_octets"] == 2000


def test_snmp_parser_json_list(tmp_path: Path) -> None:
    """Test SNMP parser with JSON list structure."""
    json_file = tmp_path / "snmp_list.json"
    data = [
        {
            "interface_id": "A->B",
            "speed": 1000000,
            "in_octets": 100,
            "out_octets": 100,
            "oper_status": "up",
        }
    ]
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    topo = SNMPParser.parse(json_file)
    assert topo.edge_count == 1
    assert ("A", "B") in topo.edges


def test_snmp_parser_json_interfaces_key(tmp_path: Path) -> None:
    """Test SNMP parser with JSON 'interfaces' key structure."""
    json_file = tmp_path / "snmp_dict.json"
    data = {
        "interfaces": [
            {
                "interface_id": "X->Y",
                "speed": 1000000,
                "in_octets": 1000,
                "out_octets": 2000,
                "oper_status": "up",
            }
        ]
    }
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    topo = SNMPParser.parse(json_file)
    assert topo.edge_count == 1
    assert topo.get_edge("X", "Y")["bandwidth"] == 1.0


def test_snmp_parser_status_mapping(tmp_path: Path) -> None:
    """Test mapping of various SNMP oper_status values."""
    csv_file = tmp_path / "status.csv"
    statuses = ["up", "down", "testing", "degraded", "1", "2", "3", "UNKNOWN"]
    expected = ["up", "down", "degraded", "degraded", "up", "down", "degraded", "up"]

    rows = []
    for i, s in enumerate(statuses):
        rows.append({"interface_id": f"N{i}->N{i+1}", "oper_status": s})

    pd.DataFrame(rows).to_csv(csv_file, index=False)
    topo = SNMPParser.parse(csv_file)

    for i, exp in enumerate(expected):
        assert topo.get_edge(f"N{i}", f"N{i+1}")["status"] == exp


def test_snmp_parser_utilization_calculation(tmp_path: Path) -> None:
    """Test utilization heuristic calculation."""
    csv_file = tmp_path / "util.csv"
    # Bandwidth = 1Mbps = 1,000,000 bps
    # Octets = 125,000 -> 1,000,000 bits
    # Default interval = 10s
    # Utilization = (1,000,000 bits) / (1,000,000 bps * 10s) = 0.1
    df = pd.DataFrame(
        {
            "interface_id": ["A->B", "C->D"],
            "speed": [1000000, 1000000],
            "in_octets": [62500, 1000000],  # 0.1 util (with out_octets)
            "out_octets": [62500, 1000000], # > 1.0 util, should be clamped
        }
    )
    df.to_csv(csv_file, index=False)

    topo = SNMPParser.parse(csv_file)
    assert pytest.approx(topo.get_edge("A", "B")["utilization"]) == 0.1
    assert topo.get_edge("C", "D")["utilization"] == 1.0


def test_snmp_parser_missing_file() -> None:
    """Test error when file does not exist."""
    with pytest.raises(IngestionError, match="SNMP export file not found"):
        SNMPParser.parse("non_existent_file.csv")


def test_snmp_parser_invalid_json_structure(tmp_path: Path) -> None:
    """Test error for invalid JSON structure."""
    json_file = tmp_path / "invalid.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"not_interfaces": []}, f)

    with pytest.raises(IngestionError, match="JSON SNMP data must be a list or contain 'interfaces' key"):
        SNMPParser.parse(json_file)


def test_snmp_parser_invalid_json_content(tmp_path: Path) -> None:
    """Test error for malformed JSON content."""
    json_file = tmp_path / "malformed.json"
    with open(json_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json }")

    with pytest.raises(IngestionError, match="Failed to read SNMP export file"):
        SNMPParser.parse(json_file)


def test_snmp_parser_missing_interface_id(tmp_path: Path) -> None:
    """Test error for missing interface_id in records."""
    csv_file = tmp_path / "missing_id.csv"
    df = pd.DataFrame({"speed": [1000000]})
    df.to_csv(csv_file, index=False)

    with pytest.raises(IngestionError, match="missing 'interface_id'"):
        SNMPParser.parse(csv_file)


def test_snmp_parser_invalid_interface_id_format(tmp_path: Path) -> None:
    """Test error for invalid interface_id format."""
    csv_file = tmp_path / "bad_id.csv"
    df = pd.DataFrame({"interface_id": ["NodeA-NodeB"], "speed": [1000000]})
    df.to_csv(csv_file, index=False)

    with pytest.raises(IngestionError, match="interface_id 'NodeA-NodeB' at index 0 is invalid"):
        SNMPParser.parse(csv_file)


def test_snmp_parser_invalid_numeric_values(tmp_path: Path) -> None:
    """Test handling of invalid numeric values (should fall back to defaults)."""
    csv_file = tmp_path / "invalid_nums.csv"
    df = pd.DataFrame(
        {
            "interface_id": ["A->B", "C->D"],
            "speed": ["invalid", 1000000],
            "in_octets": [100, "invalid"],
        }
    )
    df.to_csv(csv_file, index=False)

    topo = SNMPParser.parse(csv_file)
    # A->B should use default bandwidth (1000.0) because 'invalid' speed failed conversion
    assert topo.get_edge("A", "B")["bandwidth"] == 1000.0
    # C->D should use 0.0 for in_octets because 'invalid' failed conversion
    assert topo.get_edge("C", "D")["in_octets"] == 0.0

    # Test invalid out_octets
    csv_file2 = tmp_path / "invalid_out.csv"
    pd.DataFrame({
        "interface_id": ["E->F"],
        "out_octets": ["bad"]
    }).to_csv(csv_file2, index=False)
    topo2 = SNMPParser.parse(csv_file2)
    assert topo2.get_edge("E", "F")["out_octets"] == 0.0
