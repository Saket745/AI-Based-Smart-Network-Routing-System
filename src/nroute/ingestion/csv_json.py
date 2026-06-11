"""CSV and JSON importers for network topologies and traffic data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from nroute.exceptions import IngestionError
from nroute.ingestion.normalizer import Normalizer

if TYPE_CHECKING:
    from nroute.core.topology import Topology
    from nroute.core.traffic import TrafficMatrix


class CSVTopologyImporter:
    """Imports network topologies from CSV edge-list files."""

    @staticmethod
    def load(path: str | Path) -> Topology:
        """
        Load topology from a CSV file.
        Expects columns: src, dst (or source, destination) and optional attributes.

        Args:
            path: Path to the CSV file.
        """
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"Topology CSV file not found: {path}")

        try:
            df = pd.read_csv(p)
        except Exception as e:
            raise IngestionError(f"Failed to read CSV file {path}: {e}") from e

        # Normalize column names for source/destination
        rename_dict = {}
        for col in df.columns:
            col_lower = col.lower().strip()
            if col_lower in {"src", "source", "from"}:
                rename_dict[col] = "source"
            elif col_lower in {"dst", "destination", "to"}:
                rename_dict[col] = "destination"
        df = df.rename(columns=rename_dict)

        if "source" not in df.columns or "destination" not in df.columns:
            raise IngestionError(
                f"CSV topology file {path} must contain source/src/from and destination/dst/to columns."
            )

        raw_edges = df.to_dict(orient="records")
        # Nodes are implicitly generated from edge endpoints
        raw_nodes: list[dict[str, str]] = []
        seen_nodes = set()
        for edge in raw_edges:
            for endpoint in ("source", "destination"):
                val = str(edge[endpoint])
                if val not in seen_nodes:
                    seen_nodes.add(val)
                    raw_nodes.append({"id": val})

        return Normalizer.normalize_topology(raw_nodes, raw_edges)


class JSONTopologyImporter:
    """Imports topologies from JSON files structured as nodes and edges."""

    @staticmethod
    def load(path: str | Path) -> Topology:
        """
        Load topology from a JSON file.
        Expects keys: "nodes" (list) and "edges" (list).

        Args:
            path: Path to the JSON file.
        """
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"Topology JSON file not found: {path}")

        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise IngestionError(f"Failed to parse JSON file {path}: {e}") from e

        if not isinstance(data, dict):
            raise IngestionError(f"JSON topology data in {path} must be a dictionary.")

        raw_nodes = data.get("nodes", [])
        raw_edges = data.get("edges", [])

        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise IngestionError("JSON topology must contain 'nodes' and 'edges' lists.")

        return Normalizer.normalize_topology(raw_nodes, raw_edges)


class CSVTrafficImporter:
    """Imports traffic matrices from CSV files."""

    @staticmethod
    def load(path: str | Path) -> TrafficMatrix:
        """
        Load a traffic matrix from a CSV file.
        Expects columns: source, destination, bytes, packets, duration, protocol, timestamp.

        Args:
            path: Path to the CSV file.
        """
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"Traffic CSV file not found: {path}")

        try:
            df = pd.read_csv(p)
        except Exception as e:
            raise IngestionError(f"Failed to read CSV file {path}: {e}") from e

        raw_records = df.to_dict(orient="records")
        return Normalizer.normalize_traffic(raw_records)
