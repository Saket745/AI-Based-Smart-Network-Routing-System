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
        if not p.is_file():
            raise IngestionError(f"SNMP export file not found: {path}")

        raw_data: list[dict[str, Any]] = []

        try:
            if p.suffix.lower() == ".json":
                with open(p, encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        raw_data = loaded
                    elif isinstance(loaded, dict) and "interfaces" in loaded:
                        raw_data = loaded["interfaces"]
                    else:
                        raise IngestionError(
                            "JSON SNMP data must be a list or contain 'interfaces' key."
                        )
            else:
                # Default to CSV
                df = pd.read_csv(p)
                raw_data = df.to_dict(orient="records")
        except Exception as e:
            if isinstance(e, IngestionError):
                raise
            raise IngestionError(f"Failed to read SNMP export file {path}: {e}") from e

        raw_nodes: list[dict[str, Any]] = []
        raw_edges: list[dict[str, Any]] = []
        seen_nodes = set()

        for idx, row in enumerate(raw_data):
            # Clean keys to lowercase
            clean_row = {k.lower().strip(): v for k, v in row.items()}

            if "interface_id" not in clean_row:
                raise IngestionError(f"SNMP record at index {idx} is missing 'interface_id'.")

            if_id = str(clean_row["interface_id"])

            # Extract source and destination from interface_id
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

            # Map SNMP values to edge attributes
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

            oper_status = clean_row.get("oper_status") or clean_row.get("ifoperstatus")
            status = "up"
            if oper_status is not None:
                status_str = str(oper_status).lower().strip()
                if status_str in {"down", "2"}:
                    status = "down"
                elif status_str in {"testing", "degraded", "3"}:
                    status = "degraded"

            try:
                in_octets = float(clean_row.get("in_octets") or clean_row.get("ifincheck") or 0.0)
            except (ValueError, TypeError):
                in_octets = 0.0

            try:
                out_octets = float(clean_row.get("out_octets") or clean_row.get("ifoutcheck") or 0.0)
            except (ValueError, TypeError):
                out_octets = 0.0

            # Derive utilization if speed is known
            utilization = 0.0
            if bandwidth > 0:
                try:
                    # Utilization over a default interval (e.g., 10s)
                    octets = in_octets + out_octets
                    # utilization = (octets * 8) / (bandwidth * 1e6 * 10)
                    # Simple heuristic: clamp to valid range
                    utilization = min(1.0, max(0.0, (octets * 8) / (bandwidth * 1e6 * 10)))
                except (ValueError, TypeError):
                    pass

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
