"""Data Ingestion Engine for network topologies and traffic telemetry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from nroute.exceptions import IngestionError
from nroute.ingestion.csv_json import (
    CSVTopologyImporter,
    CSVTrafficImporter,
    JSONTopologyImporter,
)
from nroute.ingestion.netflow import NetFlowParser
from nroute.ingestion.pcap import PcapParser
from nroute.ingestion.snmp import SNMPParser

if TYPE_CHECKING:
    from nroute.core.topology import Topology
    from nroute.core.traffic import TrafficMatrix


def _ingest_explicit_format(p: Path, fmt: str, raw_format: str | None) -> Topology | TrafficMatrix:
    """Route ingestion for an explicitly specified format."""
    if fmt == "csv-topology":
        return CSVTopologyImporter.load(p)
    if fmt == "json-topology":
        return JSONTopologyImporter.load(p)
    if fmt == "csv-traffic":
        return CSVTrafficImporter.load(p)
    if fmt == "netflow":
        return NetFlowParser.parse(p)
    if fmt == "pcap":
        return PcapParser.parse(p)
    if fmt == "snmp":
        return SNMPParser.parse(p)

    raise IngestionError(
        f"Unknown ingestion format '{raw_format}'. Supported formats: "
        "csv-topology, json-topology, csv-traffic, netflow, pcap, snmp."
    )


def _auto_detect_json(p: Path) -> Topology | TrafficMatrix:
    """Auto-detect JSON data structure and route to appropriate parser/importer."""
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            if "nodes" in data and "edges" in data:
                return JSONTopologyImporter.load(p)
            if "interfaces" in data:
                return SNMPParser.parse(p)
        raise IngestionError("Unable to auto-detect JSON structure.")
    except Exception as e:
        if isinstance(e, IngestionError):
            raise
        raise IngestionError(f"Failed to auto-detect JSON format: {e}") from e


def _auto_detect_csv(p: Path, original_path: str | Path) -> Topology | TrafficMatrix:
    """Auto-detect CSV header column structure and route to appropriate parser/importer."""
    try:
        df_sample = pd.read_csv(p, nrows=1)
        cols = {col.lower().strip() for col in df_sample.columns}
    except Exception as e:
        raise IngestionError(f"Failed to read CSV headers for auto-detection: {e}") from e

    # Heuristics based on headers
    if any(h in cols for h in {"src_addr", "srcaddr", "ipv4_src_addr", "first_switched"}):
        return NetFlowParser.parse(p)
    if any(h in cols for h in {"interface_id", "oper_status", "admin_status"}):
        return SNMPParser.parse(p)
    if all(h in cols for h in {"source", "destination", "bytes", "packets"}):
        return CSVTrafficImporter.load(p)
    if any(h in cols for h in {"src", "source", "from"}) and any(
        h in cols for h in {"dst", "destination", "to"}
    ):
        return CSVTopologyImporter.load(p)

    raise IngestionError(
        f"Unable to auto-detect CSV structure for {original_path}. "
        f"Columns found: {list(df_sample.columns)}. "
        "Please specify 'format' explicitly."
    )


def ingest(path: str | Path, format: str | None = None) -> Topology | TrafficMatrix:
    """
    Ingest network data (topology or traffic) from a file.
    If format is None, auto-detects the format from extension and file contents.

    Supported formats:
    - "csv-topology": Edge-list CSV topology
    - "json-topology": Nodes and edges JSON topology
    - "csv-traffic": Flow list CSV traffic matrix
    - "netflow": CSV exported NetFlow records
    - "pcap": Binary packet capture file (aggregates to traffic matrix)
    - "snmp": SNMP counter export (CSV/JSON)

    Args:
        path: Path to the file to ingest.
        format: Optional explicit format override.

    Returns:
        Topology or TrafficMatrix object.

    Raises:
        IngestionError: If file not found, parsing fails, or format is unknown.
    """
    p = Path(path)
    if not p.is_file():
        raise IngestionError(f"Ingestion source file not found: {path}")

    fmt = format.lower().strip() if format is not None else None

    # 1. Explicit format routing
    if fmt is not None:
        return _ingest_explicit_format(p, fmt, format)

    # 2. Auto-detection logic based on extension
    suffix = p.suffix.lower()

    if suffix in {".pcap", ".pcapng"}:
        return PcapParser.parse(p)

    if suffix in {".nf", ".flow", ".nf9"}:
        return NetFlowParser.parse(p)

    if suffix == ".json":
        return _auto_detect_json(p)

    if suffix == ".csv":
        return _auto_detect_csv(p, path)

    raise IngestionError(
        f"Unable to auto-detect format for file extension '{suffix}'. "
        "Please specify 'format' explicitly."
    )
