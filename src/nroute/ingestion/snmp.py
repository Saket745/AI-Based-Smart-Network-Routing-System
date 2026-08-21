"""SNMP interface counter parser for network route optimizer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from nroute.exceptions import IngestionError
from nroute.ingestion.normalizer import Normalizer

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class SNMPParser:
    """Parses SNMP exported counter dumps into network Topologies."""

    @staticmethod
    def _load_raw_data(p: Path) -> list[dict[str, Any]]:
        if not p.is_file():
            raise IngestionError(f"SNMP export file not found: {p}")

        try:
            if p.suffix.lower() == ".json":
                with open(p, encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        return list(loaded)
                    if (
                        isinstance(loaded, dict)
                        and "interfaces" in loaded
                        and isinstance(loaded["interfaces"], list)
                    ):
                        return list(loaded["interfaces"])
                    raise IngestionError(
                        "JSON SNMP data must be a list or contain 'interfaces' key."
                    )
            else:
                df = pd.read_csv(p)
                records: list[dict[str, Any]] = df.to_dict(orient="records")
                return records
        except Exception as e:
            if isinstance(e, IngestionError):
                raise
            raise IngestionError(f"Failed to read SNMP export file {p}: {e}") from e

    @staticmethod
    def _extract_endpoints(clean_row: dict[str, Any], idx: int) -> tuple[str, str]:
        if "interface_id" not in clean_row:
            raise IngestionError(f"SNMP record at index {idx} is missing 'interface_id'.")

        if_id = str(clean_row["interface_id"])
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
        speed = clean_row.get("speed") or clean_row.get("ifspeed")
        bandwidth = 1000.0  # default bandwidth in Mbps
        if speed is not None:
            try:
                raw_speed = float(speed)
                bandwidth = raw_speed / 1e6 if raw_speed >= 10000 else raw_speed
            except (ValueError, TypeError):
                pass
        return bandwidth

    @staticmethod
    def _parse_status(clean_row: dict[str, Any]) -> str:
        oper_status = clean_row.get("oper_status") or clean_row.get("ifoperstatus")
        if oper_status is not None:
            status_str = str(oper_status).lower().strip()
            if status_str in {"down", "2"}:
                return "down"
            if status_str in {"testing", "degraded", "3"}:
                return "degraded"
        return "up"

    @staticmethod
    def _parse_octets(clean_row: dict[str, Any]) -> tuple[float, float]:
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
    def _calculate_utilization(in_octets: float, out_octets: float, bandwidth: float) -> float:
        if bandwidth <= 0:
            return 0.0
        try:
            octets = in_octets + out_octets
            return min(1.0, max(0.0, (octets * 8) / (bandwidth * 1e6 * 10)))
        except (ValueError, TypeError):
            return 0.0

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
        p = Path(path)
        raw_data = SNMPParser._load_raw_data(p)

        raw_nodes: list[dict[str, Any]] = []
        raw_edges: list[dict[str, Any]] = []
        seen_nodes = set()

        for idx, row in enumerate(raw_data):
            clean_row = {k.lower().strip(): v for k, v in row.items()}
            src, dst = SNMPParser._extract_endpoints(clean_row, idx)
            bandwidth = SNMPParser._parse_bandwidth(clean_row)
            status = SNMPParser._parse_status(clean_row)
            in_octets, out_octets = SNMPParser._parse_octets(clean_row)
            utilization = SNMPParser._calculate_utilization(in_octets, out_octets, bandwidth)

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

            for node in (src, dst):
                if node not in seen_nodes:
                    seen_nodes.add(node)
                    raw_nodes.append({"id": node, "type": "router", "status": "up"})

        return Normalizer.normalize_topology(raw_nodes, raw_edges)
