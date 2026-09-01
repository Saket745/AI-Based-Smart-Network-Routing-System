"""PCAP packet capture parser for network route optimizer."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from nroute.exceptions import IngestionError, ValidationError
from nroute.ingestion.normalizer import Normalizer
from nroute.utils.validators import validate_file_path

if TYPE_CHECKING:
    from pathlib import Path

    from nroute.core.traffic import TrafficMatrix


class PcapParser:
    """Parses binary PCAP files and extracts IP flow traffic summaries."""

    @staticmethod
    def _map_protocol(proto_num: int) -> str:
        """Map IP protocol number to standard protocol string."""
        if proto_num == 6:
            return "TCP"
        if proto_num == 17:
            return "UDP"
        if proto_num == 1:
            return "ICMP"
        return f"PROTO_{proto_num}"

    @staticmethod
    def _read_pcap_flows(
        file_path: Path,
        max_packets: int,
        ip_layer_cls: type,
        pcap_reader_cls: type,
    ) -> dict[tuple[str, str, str], dict[str, Any]]:
        """
        Read up to max_packets from a PCAP file and aggregate flow metrics.
        """
        try:
            p = validate_file_path(path, must_exist=True)
        except ValidationError as e:
            raise IngestionError(f"Invalid PCAP file path: {e}") from e

        # Lazy import scapy to minimize start-up time
        try:
            from scapy.layers.inet import IP
            from scapy.utils import PcapReader
        except ImportError as e:
            raise IngestionError(
                "Optional dependency 'scapy' is required for PCAP parsing. "
                "Install with 'pip install nroute[pcap]'."
            ) from e

        # Store aggregations of flows
        # Key: (src_ip, dst_ip, protocol_str)
        # Value: dict with keys: bytes, packets, first_time, last_time
        flow_aggregations: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
            lambda: {
                "bytes": 0,
                "packets": 0,
                "first_time": None,
                "last_time": None,
            }
        )

        packet_count = 0
        with pcap_reader_cls(str(file_path)) as pcap_reader:
            for pkt in pcap_reader:
                if packet_count >= max_packets:
                    break

                if pkt.haslayer(ip_layer_cls):
                    ip_layer = pkt[ip_layer_cls]
                    src = str(ip_layer.src)
                    dst = str(ip_layer.dst)
                    proto = PcapParser._map_protocol(int(ip_layer.proto))

                    pkt_len = len(pkt)
                    pkt_time = float(pkt.time)

                    flow = flow_aggregations[(src, dst, proto)]
                    flow["bytes"] += pkt_len
                    flow["packets"] += 1

                    if flow["first_time"] is None or pkt_time < flow["first_time"]:
                        flow["first_time"] = pkt_time
                    if flow["last_time"] is None or pkt_time > flow["last_time"]:
                        flow["last_time"] = pkt_time

                    packet_count += 1

        return flow_aggregations

    @staticmethod
    def _build_raw_records(
        flow_aggregations: dict[tuple[str, str, str], dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert flow aggregations into raw dictionary records."""
        raw_records = []
        for (src, dst, proto), metrics in flow_aggregations.items():
            first = metrics["first_time"] or 0.0
            last = metrics["last_time"] or 0.0
            duration = max(0.0, last - first)

            raw_records.append(
                {
                    "source": src,
                    "destination": dst,
                    "bytes": metrics["bytes"],
                    "packets": metrics["packets"],
                    "duration": duration,
                    "protocol": proto,
                    "timestamp": first,
                }
            )
        return raw_records

    @staticmethod
    def parse(path: str | Path) -> TrafficMatrix:
        """
        Read a PCAP file and aggregate packet info into flow records.
        Limits parsing to first 100,000 packets to prevent excessive execution time.

        Args:
            path: Path to the PCAP file.
        """
        try:
            p = validate_file_path(path, must_exist=True)
        except ValidationError as exc:
            raise IngestionError(f"Invalid PCAP file path '{path}': {exc}") from exc

        # Lazy import scapy to minimize start-up time
        try:
            from scapy.layers.inet import IP
            from scapy.utils import PcapReader
        except ImportError as e:
            raise IngestionError(
                "Scapy library is required for PCAP parsing. Run 'pip install scapy'."
            ) from e

        try:
            flow_aggregations = PcapParser._read_pcap_flows(p, 100000, IP, PcapReader)
        except Exception as e:
            raise IngestionError(f"Failed to parse PCAP file {path}: {e}") from e

        raw_records = PcapParser._build_raw_records(flow_aggregations)
        return Normalizer.normalize_traffic(raw_records)
