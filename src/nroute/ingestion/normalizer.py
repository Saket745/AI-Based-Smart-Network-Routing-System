"""Common normalization layer for network data ingestion."""

from __future__ import annotations

from typing import Any

from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord, TrafficMatrix
from nroute.exceptions import IngestionError


def _get_field(mapping: dict[str, Any], *keys: str) -> Any:
    """Retrieve the first matching key from mapping where value is not None."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


class Normalizer:
    """
    Normalizes and validates raw data into core nroute classes (Topology, TrafficMatrix).
    """

    @staticmethod
    def normalize_topology(
        raw_nodes: list[dict[str, Any]], raw_edges: list[dict[str, Any]]
    ) -> Topology:
        """
        Normalize raw nodes and edges and load them into a Topology.

        Args:
            raw_nodes: List of dictionaries representing nodes.
            raw_edges: List of dictionaries representing edges.

        Returns:
            A validated Topology instance.

        Raises:
            IngestionError: If validation or normalization fails.
        """
        topo = Topology()

        # 1. Normalize and add nodes
        for idx, node in enumerate(raw_nodes):
            node_id = _get_field(node, "id", "name")
            if node_id is None:
                raise IngestionError(f"Node at index {idx} is missing 'id' or 'name'.")

            # Clean keys to lowercase
            attrs = {k.lower(): v for k, v in node.items() if k.lower() not in {"id", "name"}}

            # Handle common variations of attributes
            if "type" not in attrs and "node_type" in attrs:
                attrs["type"] = attrs.pop("node_type")

            try:
                topo.add_node(str(node_id), **attrs)
            except Exception as e:
                raise IngestionError(f"Failed to normalize node '{node_id}': {e}") from e

        # 2. Normalize and add edges
        for idx, edge in enumerate(raw_edges):
            src = _get_field(edge, "source", "src", "from")
            dst = _get_field(edge, "destination", "dst", "to", "target")

            if src is None or dst is None:
                raise IngestionError(
                    f"Edge at index {idx} is missing source ('source'/'src'/'from') "
                    "or destination ('destination'/'dst'/'to'/'target') node ID."
                )

            src_str = str(src)
            dst_str = str(dst)

            # Ensure nodes exist in topology, if not auto-create them with defaults
            if src_str not in topo.nodes:
                topo.add_node(src_str)
            if dst_str not in topo.nodes:
                topo.add_node(dst_str)

            # Clean and map edge attributes to standard keys
            attrs = {
                k.lower(): v
                for k, v in edge.items()
                if k.lower() not in {"source", "src", "from", "destination", "dst", "to"}
            }

            # Common overrides
            if "bandwidth" not in attrs and "speed" in attrs:
                attrs["bandwidth"] = attrs.pop("speed")

            try:
                topo.add_edge(src_str, dst_str, **attrs)
            except Exception as e:
                raise IngestionError(
                    f"Failed to normalize edge from '{src_str}' to '{dst_str}': {e}"
                ) from e

        return topo

    @staticmethod
    def normalize_traffic(raw_records: list[dict[str, Any]]) -> TrafficMatrix:
        """
        Normalize raw flow records and load them into a TrafficMatrix.

        Args:
            raw_records: List of dictionaries representing flow records.

        Returns:
            A validated TrafficMatrix.

        Raises:
            IngestionError: If validation fails.
        """
        flows = []
        for idx, record in enumerate(raw_records):
            # Map common alternate field names
            source = _get_field(record, "source", "src", "src_ip", "src_addr")
            destination = _get_field(record, "destination", "dst", "dst_ip", "dst_addr")
            num_bytes = _get_field(record, "bytes", "octets", "doctets", "dOctets")
            packets = _get_field(record, "packets", "pkts", "dpkts", "dPkts")
            duration = _get_field(record, "duration")
            protocol = _get_field(record, "protocol", "proto")
            timestamp = _get_field(record, "timestamp", "time", "first_switched", "last_switched")

            if (
                source is None
                or destination is None
                or num_bytes is None
                or packets is None
                or protocol is None
            ):
                raise IngestionError(
                    f"Flow record at index {idx} is missing required fields. Record: {record}"
                )

            # Clean duration and timestamp defaults
            if duration is None:
                duration = 0.0
            if timestamp is None:
                timestamp = 0.0

            try:
                flows.append(
                    FlowRecord(
                        source=str(source),
                        destination=str(destination),
                        bytes=int(num_bytes),
                        packets=int(packets),
                        duration=float(duration),
                        protocol=str(protocol),
                        timestamp=float(timestamp),
                    )
                )
            except Exception as e:
                raise IngestionError(f"Failed to normalize flow record at index {idx}: {e}") from e

        return TrafficMatrix(flows=flows)
