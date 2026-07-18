"""Traffic models including FlowRecord and TrafficMatrix."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field

from nroute.exceptions import IngestionError


class FlowRecord(BaseModel):
    """
    Represents a single flow record (NetFlow/pcap flow summary).
    """

    source: str = Field(..., description="Source node ID")
    destination: str = Field(..., description="Destination node ID")
    bytes: int = Field(..., ge=0, description="Total bytes in flow")
    packets: int = Field(..., ge=0, description="Total packets in flow")
    duration: float = Field(..., ge=0.0, description="Flow duration in seconds")
    protocol: str = Field(..., description="Network protocol (e.g., TCP, UDP, ICMP)")
    timestamp: float = Field(..., ge=0.0, description="Flow timestamp (epoch or tick)")


class TrafficMatrix(BaseModel):
    """
    Collection of flow records representing traffic patterns in the network.
    """

    flows: list[FlowRecord] = Field(default_factory=list, description="List of flow records")

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the traffic matrix to a pandas DataFrame.

        Returns:
            A pandas DataFrame with flow record columns.
        """
        if not self.flows:
            return pd.DataFrame(
                columns=[
                    "source",
                    "destination",
                    "bytes",
                    "packets",
                    "duration",
                    "protocol",
                    "timestamp",
                ]
            )
        data = [flow.model_dump() for flow in self.flows]
        return pd.DataFrame(data)

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> TrafficMatrix:
        """
        Create a TrafficMatrix from a pandas DataFrame.

        Args:
            df: A pandas DataFrame containing flow record columns.

        Returns:
            A reconstructed TrafficMatrix.

        Raises:
            IngestionError: If the DataFrame contains invalid/missing columns.
        """
        required_cols = {
            "source",
            "destination",
            "bytes",
            "packets",
            "duration",
            "protocol",
            "timestamp",
        }
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise IngestionError(f"DataFrame is missing required flow columns: {missing_cols}.")

        flows = []
        indices = df.index
        sources = df["source"]
        destinations = df["destination"]
        bytes_col = df["bytes"]
        packets_col = df["packets"]
        durations = df["duration"]
        protocols = df["protocol"]
        timestamps = df["timestamp"]

        for idx, src, dst, byt, pkt, dur, proto, ts in zip(
            indices,
            sources,
            destinations,
            bytes_col,
            packets_col,
            durations,
            protocols,
            timestamps,
            strict=True,
        ):
            try:
                flows.append(
                    FlowRecord(
                        source=str(src),
                        destination=str(dst),
                        bytes=int(byt),
                        packets=int(pkt),
                        duration=float(dur),
                        protocol=str(proto),
                        timestamp=float(ts),
                    )
                )
            except Exception as e:
                raise IngestionError(f"Failed to parse flow record at row {idx}: {e}") from e

        return cls(flows=flows)

    @classmethod
    def from_csv(cls, path: str | Path) -> TrafficMatrix:
        """
        Load a traffic matrix from a CSV file.

        Args:
            path: Path to the CSV file.

        Returns:
            A TrafficMatrix instance.
        """
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"Traffic CSV file does not exist: {path}")
        try:
            df = pd.read_csv(p)
            return cls.from_dataframe(df)
        except Exception as e:
            if isinstance(e, IngestionError):
                raise
            raise IngestionError(f"Failed to read traffic data from CSV {path}: {e}") from e

    def filter_by_time(self, start: float, end: float) -> TrafficMatrix:
        """
        Filter flow records within a specific time window.

        Args:
            start: Start timestamp (inclusive).
            end: End timestamp (inclusive).

        Returns:
            A new TrafficMatrix containing filtered flows.
        """
        filtered = [f for f in self.flows if start <= f.timestamp <= end]
        return TrafficMatrix(flows=filtered)

    def summary(self) -> str:
        """
        Generate a text summary of the traffic matrix.

        Returns:
            A multiline summary string.
        """
        if not self.flows:
            return "Empty Traffic Matrix (0 flows)"

        total_bytes = sum(f.bytes for f in self.flows)
        total_packets = sum(f.packets for f in self.flows)
        unique_sources = len({f.source for f in self.flows})
        unique_dests = len({f.destination for f in self.flows})
        protocols: dict[str, int] = {}
        for f in self.flows:
            protocols[f.protocol] = protocols.get(f.protocol, 0) + 1

        protocol_str = ", ".join(f"{proto}: {count}" for proto, count in sorted(protocols.items()))

        return (
            f"Traffic Matrix Summary:\n"
            f"----------------------\n"
            f"Total Flows: {len(self.flows)}\n"
            f"Total volume: {total_bytes:,} bytes ({total_packets:,} packets)\n"
            f"Unique Sources: {unique_sources}\n"
            f"Unique Destinations: {unique_dests}\n"
            f"Protocols: {protocol_str}\n"
        )
