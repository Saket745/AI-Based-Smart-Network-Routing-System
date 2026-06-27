"""Unit tests for the Ingestion and Telemetry Parser Agent."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from nroute.core.topology import Topology
from nroute.core.traffic import TrafficMatrix
from nroute.exceptions import IngestionError
from nroute.ingestion import ingest
from nroute.ingestion.csv_json import (
    CSVTopologyImporter,
    CSVTrafficImporter,
    JSONTopologyImporter,
)
from nroute.ingestion.netflow import NetFlowParser
from nroute.ingestion.pcap import PcapParser

if TYPE_CHECKING:
    from pathlib import Path


# Mock packet helper for Scapy PcapReader tests
class MockIP:
    def __init__(self, src: str, dst: str, proto: int):
        self.src = src
        self.dst = dst
        self.proto = proto


class MockPacket:
    def __init__(self, src: str, dst: str, proto: int, length: int, time: float):
        self.ip = MockIP(src, dst, proto)
        self.length = length
        self.time = time

    def haslayer(self, layer_class: Any) -> bool:
        return True

    def __getitem__(self, item: Any) -> MockIP:
        return self.ip

    def __len__(self) -> int:
        return self.length


def test_csv_topology_importer_valid(tmp_path: Path) -> None:
    """Test importing topology from CSV with various headers."""
    csv_file = tmp_path / "topo.csv"

    # 1. Standard headers (src, dst, bandwidth, latency)
    df = pd.DataFrame(
        {"src": ["A", "B"], "dst": ["B", "C"], "bandwidth": [1000.0, 500.0], "latency": [5.0, 10.0]}
    )
    df.to_csv(csv_file, index=False)

    topo = CSVTopologyImporter.load(csv_file)
    assert topo.node_count == 3
    assert topo.edge_count == 2
    assert "A" in topo.nodes
    assert topo.get_edge("A", "B")["bandwidth"] == 1000.0
    assert topo.get_edge("A", "B")["latency"] == 5.0

    # 2. Alternative headers (from, to, speed)
    df_alt = pd.DataFrame(
        {"from": ["X", "Y"], "to": ["Y", "Z"], "speed": [100.0, 200.0], "status": ["up", "down"]}
    )
    df_alt.to_csv(csv_file, index=False)

    topo_alt = CSVTopologyImporter.load(csv_file)
    assert topo_alt.node_count == 3
    assert topo_alt.get_edge("X", "Y")["bandwidth"] == 100.0
    assert topo_alt.get_edge("Y", "Z")["status"] == "down"


def test_csv_topology_importer_invalid(tmp_path: Path) -> None:
    """Test invalid files and formats for CSV topology parser."""
    csv_file = tmp_path / "invalid_topo.csv"

    # Missing columns
    df = pd.DataFrame({"something": ["A", "B"], "other": ["B", "C"]})
    df.to_csv(csv_file, index=False)

    with pytest.raises(IngestionError, match="must contain source/src/from"):
        CSVTopologyImporter.load(csv_file)

    # Missing file
    with pytest.raises(IngestionError, match="Topology CSV file not found"):
        CSVTopologyImporter.load(tmp_path / "non_existent.csv")


def test_json_topology_importer_valid(tmp_path: Path) -> None:
    """Test importing topology from JSON file."""
    json_file = tmp_path / "topo.json"

    data = {
        "nodes": [
            {"id": "A", "type": "router", "capacity": 1000.0},
            {"name": "B", "type": "switch"},
        ],
        "edges": [{"source": "A", "destination": "B", "bandwidth": 100.0}],
    }
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    topo = JSONTopologyImporter.load(json_file)
    assert topo.node_count == 2
    assert topo.edge_count == 1
    assert topo.get_node("A")["type"] == "router"
    assert topo.get_node("B")["type"] == "switch"
    assert topo.get_edge("A", "B")["bandwidth"] == 100.0


def test_json_topology_importer_invalid(tmp_path: Path) -> None:
    """Test JSON topology importer errors."""
    json_file = tmp_path / "bad.json"

    # Empty JSON
    with open(json_file, "w", encoding="utf-8") as f:
        f.write("")
    with pytest.raises(IngestionError, match="Failed to parse JSON file"):
        JSONTopologyImporter.load(json_file)

    # Non-dictionary structure
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump([1, 2, 3], f)
    with pytest.raises(IngestionError, match="must be a dictionary"):
        JSONTopologyImporter.load(json_file)

    # Missing nodes/edges keys
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": "not_a_list", "edges": []}, f)
    with pytest.raises(IngestionError, match="must contain 'nodes' and 'edges'"):
        JSONTopologyImporter.load(json_file)


def test_csv_traffic_importer(tmp_path: Path) -> None:
    """Test importing traffic from CSV."""
    csv_file = tmp_path / "traffic.csv"

    df = pd.DataFrame(
        {
            "source": ["A", "B"],
            "destination": ["B", "C"],
            "bytes": [1000, 2000],
            "packets": [10, 20],
            "duration": [1.5, 2.0],
            "protocol": ["TCP", "UDP"],
            "timestamp": [100.0, 101.5],
        }
    )
    df.to_csv(csv_file, index=False)

    tm = CSVTrafficImporter.load(csv_file)
    assert len(tm.flows) == 2
    assert tm.flows[0].source == "A"
    assert tm.flows[0].bytes == 1000
    assert tm.flows[1].protocol == "UDP"


def test_netflow_parser_valid(tmp_path: Path) -> None:
    """Test NetFlow CSV parser with duration calculation and column renaming."""
    csv_file = tmp_path / "netflow.csv"

    df = pd.DataFrame(
        {
            "srcaddr": ["10.0.0.1", "10.0.0.2"],
            "dstaddr": ["10.0.0.2", "10.0.0.3"],
            "octets": [5000, 3000],
            "pkts": [10, 6],
            "first_switched": [1000.1, 1002.5],
            "last_switched": [1002.3, 1002.0],  # Second record has negative duration
            "protocol": ["TCP", "UDP"],
        }
    )
    df.to_csv(csv_file, index=False)

    tm = NetFlowParser.parse(csv_file)
    assert len(tm.flows) == 2
    assert tm.flows[0].source == "10.0.0.1"
    assert tm.flows[0].bytes == 5000

    # First record duration should be 1002.3 - 1000.1 = 2.2
    assert pytest.approx(tm.flows[0].duration) == 2.2

    # Second record duration should be 1002.0 - 1002.5 = -0.5, clipped to 0.0
    assert tm.flows[1].duration == 0.0


def test_netflow_parser_missing_fields(tmp_path: Path) -> None:
    """Test NetFlow CSV parser errors for missing fields."""
    csv_file = tmp_path / "bad_netflow.csv"
    df = pd.DataFrame({"srcaddr": ["10.0.0.1"], "dstaddr": ["10.0.0.2"]})
    df.to_csv(csv_file, index=False)

    with pytest.raises(IngestionError, match="missing required columns"):
        NetFlowParser.parse(csv_file)


@patch("scapy.utils.PcapReader")
def test_pcap_parser(mock_pcap_reader_cls: MagicMock, tmp_path: Path) -> None:
    """Test PCAP parser by mocking Scapy's PcapReader."""
    pcap_file = tmp_path / "test.pcap"
    pcap_file.touch()

    # Construct mock packets
    p1 = MockPacket("10.0.0.1", "10.0.0.2", 6, 100, 1000.0)  # TCP
    p2 = MockPacket("10.0.0.1", "10.0.0.2", 6, 150, 1001.5)  # TCP
    p3 = MockPacket("10.0.0.2", "10.0.0.3", 17, 80, 1002.0)  # UDP
    p4 = MockPacket("10.0.0.3", "10.0.0.1", 1, 64, 1003.0)  # ICMP
    p5 = MockPacket("10.0.0.1", "10.0.0.3", 99, 1000, 1004.0)  # PROTO_99

    # Mock context manager behavior
    mock_pcap_reader = MagicMock()
    mock_pcap_reader.__enter__.return_value = [p1, p2, p3, p4, p5]
    mock_pcap_reader_cls.return_value = mock_pcap_reader

    tm = PcapParser.parse(pcap_file)
    assert len(tm.flows) == 4

    # Check aggregation of TCP flow (p1 and p2)
    tcp_flow = next(f for f in tm.flows if f.protocol == "TCP")
    assert tcp_flow.source == "10.0.0.1"
    assert tcp_flow.destination == "10.0.0.2"
    assert tcp_flow.bytes == 250
    assert tcp_flow.packets == 2
    assert pytest.approx(tcp_flow.duration) == 1.5
    assert tcp_flow.timestamp == 1000.0

    # Check other protocols
    assert any(f.protocol == "UDP" for f in tm.flows)
    assert any(f.protocol == "ICMP" for f in tm.flows)
    assert any(f.protocol == "PROTO_99" for f in tm.flows)


def test_unified_ingest_explicit_and_auto_detect(tmp_path: Path) -> None:
    """Test the unified ingest() function with format overrides and auto-detection."""
    # 1. Non-existent file
    with pytest.raises(IngestionError, match="source file not found"):
        ingest("non_existent.csv")

    # 2. Unknown explicit format
    csv_file = tmp_path / "test.csv"
    csv_file.touch()
    with pytest.raises(IngestionError, match="Unknown ingestion format"):
        ingest(csv_file, format="invalid-format")

    # 3. Auto-detect JSON: Topology
    json_file = tmp_path / "test_topo.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": [], "edges": []}, f)
    result = ingest(json_file)
    assert isinstance(result, Topology)

    # 4. Auto-detect JSON: SNMP
    json_snmp_file = tmp_path / "test_snmp.json"
    with open(json_snmp_file, "w", encoding="utf-8") as f:
        json.dump({"interfaces": []}, f)
    result = ingest(json_snmp_file)
    assert isinstance(result, Topology)

    # 5. Auto-detect JSON: Bad structure
    json_bad_file = tmp_path / "test_bad.json"
    with open(json_bad_file, "w", encoding="utf-8") as f:
        json.dump({"something_else": 123}, f)
    with pytest.raises(IngestionError, match="Unable to auto-detect JSON structure"):
        ingest(json_bad_file)

    # 6. Auto-detect CSV NetFlow
    csv_nf = tmp_path / "test_nf.csv"
    df_nf = pd.DataFrame(
        {
            "first_switched": [10],
            "src_addr": ["10.0.0.1"],
            "dst_addr": ["10.0.0.2"],
            "bytes": [100],
            "packets": [1],
            "protocol": ["TCP"],
        }
    )
    df_nf.to_csv(csv_nf, index=False)
    result = ingest(csv_nf)
    assert isinstance(result, TrafficMatrix)

    # 7. Auto-detect CSV SNMP
    csv_snmp = tmp_path / "test_snmp.csv"
    df_snmp = pd.DataFrame({"interface_id": ["A->B"], "oper_status": ["up"]})
    df_snmp.to_csv(csv_snmp, index=False)
    result = ingest(csv_snmp)
    assert isinstance(result, Topology)

    # 8. Auto-detect CSV Traffic Matrix
    csv_tm = tmp_path / "test_tm.csv"
    df_tm = pd.DataFrame(
        {"source": ["A"], "destination": ["B"], "bytes": [100], "packets": [1], "protocol": ["TCP"]}
    )
    df_tm.to_csv(csv_tm, index=False)
    result = ingest(csv_tm)
    assert isinstance(result, TrafficMatrix)

    # 9. Auto-detect CSV Topology
    csv_topo = tmp_path / "test_topo.csv"
    df_topo = pd.DataFrame({"from": ["A"], "to": ["B"]})
    df_topo.to_csv(csv_topo, index=False)
    result = ingest(csv_topo)
    assert isinstance(result, Topology)

    # 10. Auto-detect unrecognized CSV
    csv_unrec = tmp_path / "test_unrec.csv"
    df_unrec = pd.DataFrame({"col1": ["A"], "col2": ["B"]})
    df_unrec.to_csv(csv_unrec, index=False)
    with pytest.raises(IngestionError, match="Unable to auto-detect CSV structure"):
        ingest(csv_unrec)


def test_topology_and_traffic_classmethods(tmp_path: Path) -> None:
    """Test from_csv, from_json, from_netflow factory classmethods on Topology/TrafficMatrix."""
    # Topology.from_csv
    csv_file = tmp_path / "topo.csv"
    pd.DataFrame({"src": ["A"], "dst": ["B"]}).to_csv(csv_file, index=False)
    topo1 = Topology.from_csv(csv_file)
    assert topo1.node_count == 2

    # Topology.from_json
    json_file = tmp_path / "topo.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"nodes": [{"id": "X"}], "edges": []}, f)
    topo2 = Topology.from_json(json_file)
    assert topo2.node_count == 1

    # TrafficMatrix.from_csv
    traffic_csv = tmp_path / "traffic.csv"
    pd.DataFrame(
        {
            "source": ["X"],
            "destination": ["Y"],
            "bytes": [1000],
            "packets": [5],
            "duration": [1.0],
            "protocol": ["TCP"],
            "timestamp": [100.0],
        }
    ).to_csv(traffic_csv, index=False)
    tm = TrafficMatrix.from_csv(traffic_csv)
    assert len(tm.flows) == 1

    # Topology.from_netflow
    netflow_csv = tmp_path / "netflow.csv"
    pd.DataFrame(
        {
            "src_addr": ["N1", "N2"],
            "dst_addr": ["N2", "N3"],
            "bytes": [1000, 2000],
            "packets": [5, 10],
            "protocol": ["TCP", "TCP"],
        }
    ).to_csv(netflow_csv, index=False)
    topo3 = Topology.from_netflow(netflow_csv)
    assert topo3.node_count == 3
    assert ("N1", "N2") in topo3.edges
    assert ("N2", "N3") in topo3.edges
