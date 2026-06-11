"""PCAP packet capture parser for network route optimizer."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nroute.exceptions import IngestionError
from nroute.ingestion.normalizer import Normalizer

if TYPE_CHECKING:
    from nroute.core.traffic import TrafficMatrix


class PcapParser:
    """Parses binary PCAP files and extracts IP flow traffic summaries."""

    @staticmethod
    def parse(path: str | Path) -> TrafficMatrix:
        """
        Read a PCAP file and aggregate packet info into flow records.
        Limits parsing to first 100,000 packets to prevent excessive execution time.

        Args:
            path: Path to the PCAP file.
        """
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"PCAP file not found: {path}")

        # Lazy import scapy to minimize start-up time
        try:
            from scapy.layers.inet import IP
            from scapy.utils import PcapReader
        except ImportError as e:
            raise IngestionError(
                "Scapy library is required for PCAP parsing. Run 'pip install scapy'."
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
        max_packets = 100000

        try:
            with PcapReader(str(p)) as pcap_reader:
                for pkt in pcap_reader:
                    if packet_count >= max_packets:
                        break

                    if pkt.haslayer(IP):
                        ip_layer = pkt[IP]
                        src = str(ip_layer.src)
                        dst = str(ip_layer.dst)
                        proto_num = int(ip_layer.proto)

                        # Standard protocol mappings
                        if proto_num == 6:
                            proto = "TCP"
                        elif proto_num == 17:
                            proto = "UDP"
                        elif proto_num == 1:
                            proto = "ICMP"
                        else:
                            proto = f"PROTO_{proto_num}"

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
        except Exception as e:
            raise IngestionError(f"Failed to parse PCAP file {path}: {e}") from e

        # Convert aggregations into raw list of dicts for Normalizer
        raw_records = []
        for (src, dst, proto), metrics in flow_aggregations.items():
            first = metrics["first_time"] or 0.0
            last = metrics["last_time"] or 0.0
            duration = max(0.0, last - first)

            raw_records.append({
                "source": src,
                "destination": dst,
                "bytes": metrics["bytes"],
                "packets": metrics["packets"],
                "duration": duration,
                "protocol": proto,
                "timestamp": first,
            })

        return Normalizer.normalize_traffic(raw_records)
