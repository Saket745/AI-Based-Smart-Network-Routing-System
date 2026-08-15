"""SNMP interface counter parser for network route optimizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pandas as pd

from nroute.exceptions import IngestionError
from nroute.ingestion.normalizer import Normalizer

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class SNMPParser:
    """Parses SNMP exported counter dumps into network Topologies."""

    @staticmethod
    def _load_raw_data(path: str | Path) -> list[dict[str, Any]]:
        """Load raw SNMP records from a JSON or CSV file."""
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"SNMP export file not found: {path}")

        try:
            if p.suffix.lower() == ".json":
                with open(p, encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        return cast("list[dict[str, Any]]", loaded)
                    elif isinstance(loaded, dict) and "interfaces" in loaded:
                        return cast("list[dict[str, Any]]", loaded["interfaces"])
                    else:
                        raise IngestionError(
                            "JSON SNMP data must be a list or contain 'interfaces' key."
                        )
            else:
                # Default to CSV
                df = pd.read_csv(p)
                records = df.to_dict(orient="records")
                return cast("list[dict[str, Any]]", records)
        except Exception as e:
            if isinstance(e, IngestionError):
                raise
            raise IngestionError(f"Failed to read SNMP export file {path}: {e}") from e

    @staticmethod
    def _extract_endpoints(if_id: str, idx: int) -> tuple[str, str]:
        """Extract source and destination endpoints from an interface ID."""
        src, dst = None, None
        for separator in ("->", "-to-", ":"):
            if separator in if_id:
                parts = if_id.split(separator, 1)
                src = parts[0].strip()
                dst = parts[1].strip()
                break

        if not src or not dst:
            raise IngestionError(
                f"SNMP interface_id '{if_id}' at index {idx} is invalid. "
                "Must specify a link connection with separator (e.g. 'NodeA->NodeB')."
            )
        return src, dst

    @staticmethod
    def _parse_bandwidth(clean_row: dict[str, Any]) -> float:
        """Parse and convert SNMP speed to bandwidth in Mbps."""
        speed = clean_row.get("speed") or clean_row.get("ifspeed")
        bandwidth = 1000.0  # default bandwidth in Mbps
        if speed is not None:
            try:
                # SNMP ifSpeed is typically in bps. Convert bps -> Mbps
                raw_speed = float(speed)
                # Heuristic: if it's very large, it's likely bps.
                # 100,000 bps = 0.1 Mbps. 1,000 Mbps = 1 Gbps.
                bandwidth = raw_speed / 1e6 if raw_speed >= 10000 else raw_speed
            except (ValueError, TypeError):
                pass
        return bandwidth

    @staticmethod
    def _parse_status(clean_row: dict[str, Any]) -> str:
        """Parse and map SNMP operational status to standard status."""
        oper_status = clean_row.get("oper_status") or clean_row.get("ifoperstatus")
        status = "up"
        if oper_status is not None:
            status_str = str(oper_status).lower().strip()
            if status_str in {"down", "2"}:
                status = "down"
            elif status_str in {"testing", "degraded", "3"}:
                status = "degraded"
        return status

    @staticmethod
    def _parse_octets(clean_row: dict[str, Any]) -> tuple[float, float]:
        """Parse in and out octets from row."""
        try:
            in_octets = float(clean_row.get("in_octets") or clean_row.get("ifincheck") or 0.0)
        except (ValueError, TypeError):
            in_octets = 0.0

        try:
            out_octets = float(clean_row.get("out_octets") or clean_row.get("ifoutcheck") or 0.0)
        except (ValueError, TypeError):
            out_octets = 0.0

        return in_octets, out_octets

    @staticmethod
    def _calculate_utilization(bandwidth: float, in_octets: float, out_octets: float) -> float:
        """Calculate and clamp utilization metric."""
        utilization = 0.0
        if bandwidth > 0:
            try:
                # Utilization over a default interval (e.g., 10s)
                octets = in_octets + out_octets
                # Simple heuristic: clamp to valid range [0.0, 1.0]
                utilization = min(1.0, max(0.0, (octets * 8) / (bandwidth * 1e6 * 10)))
            except (ValueError, TypeError):
                pass
        return utilization

    @staticmethod
    def parse(path: str | Path) -> Topology:
        """
        Parse exported SNMP counter dumps (CSV or JSON).

        Expects columns/keys:
        interface_id, speed, in_octets, out_octets, admin_status, oper_status

        The interface_id must define the connection endpoints, e.g., "NodeA->NodeB"

        Args:
            path: Path to the SNMP export dump file.
        """
        raw_data = SNMPParser._load_raw_data(path)

        raw_nodes: list[dict[str, Any]] = []
        raw_edges: list[dict[str, Any]] = []
        seen_nodes = set()

        for idx, row in enumerate(raw_data):
            # Clean keys to lowercase
            clean_row = {k.lower().strip(): v for k, v in row.items()}

            if "interface_id" not in clean_row:
                raise IngestionError(f"SNMP record at index {idx} is missing 'interface_id'.")

            if_id = str(clean_row["interface_id"])
            src, dst = SNMPParser._extract_endpoints(if_id, idx)

            bandwidth = SNMPParser._parse_bandwidth(clean_row)
            status = SNMPParser._parse_status(clean_row)
            in_octets, out_octets = SNMPParser._parse_octets(clean_row)
            utilization = SNMPParser._calculate_utilization(bandwidth, in_octets, out_octets)

            edge_attr = {
                "source": src,
                "destination": dst,
                "bandwidth": bandwidth,
                "status": status,
                "utilization": utilization,
                "in_octets": in_octets,
                "out_octets": out_octets,
            }
            raw_edges.append(edge_attr)

            # Add endpoints to nodes list
            for node in (src, dst):
                if node not in seen_nodes:
                    seen_nodes.add(node)
                    raw_nodes.append(
                        {
                            "id": node,
                            "type": "router",
                            "status": "up",
                        }
                    )

        return Normalizer.normalize_topology(raw_nodes, raw_edges)
