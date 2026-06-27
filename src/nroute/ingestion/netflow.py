"""NetFlow CSV export parser for network route optimizer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from nroute.exceptions import IngestionError
from nroute.ingestion.normalizer import Normalizer

if TYPE_CHECKING:
    from nroute.core.traffic import TrafficMatrix


class NetFlowParser:
    """Parses NetFlow flow records exported as CSV datasets."""

    @staticmethod
    def parse(path: str | Path) -> TrafficMatrix:
        """
        Parse exported NetFlow CSV data.

        Expects columns like:
        src_addr, dst_addr, bytes, packets, first_switched, last_switched, protocol

        Args:
            path: Path to the CSV NetFlow file.
        """
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"NetFlow CSV file not found: {path}")

        try:
            df = pd.read_csv(p)
        except Exception as e:
            raise IngestionError(f"Failed to read NetFlow CSV file {path}: {e}") from e

        # Normalize typical NetFlow header variations to standard labels
        rename_map = {}
        for col in df.columns:
            cleaned = col.lower().strip().replace(" ", "_")
            if cleaned in {"src_addr", "srcaddr", "ipv4_src_addr", "src", "source"}:
                rename_map[col] = "source"
            elif cleaned in {
                "dst_addr",
                "dstaddr",
                "ipv4_dst_addr",
                "dst",
                "destination",
            }:
                rename_map[col] = "destination"
            elif cleaned in {"bytes", "octets", "inoctets", "d_octets", "doctets"}:
                rename_map[col] = "bytes"
            elif cleaned in {"packets", "pkts", "inpkts", "d_pkts", "dpkts"}:
                rename_map[col] = "packets"
            elif cleaned in {"protocol", "proto", "pr"}:
                rename_map[col] = "protocol"
            elif cleaned in {
                "first_switched",
                "first",
                "start_time",
                "timestamp",
                "time",
            }:
                rename_map[col] = "timestamp"

        df = df.rename(columns=rename_map)

        # Ensure required columns exist
        required = {"source", "destination", "bytes", "packets", "protocol"}
        missing = required - set(df.columns)
        if missing:
            raise IngestionError(
                f"NetFlow CSV file is missing required columns: {missing}. "
                f"Available columns: {list(df.columns)}"
            )

        # Handle duration derivation if start and end switches are present
        if "duration" not in df.columns:
            if "last_switched" in df.columns and "timestamp" in df.columns:
                df["duration"] = df["last_switched"] - df["timestamp"]
            elif "last" in df.columns and "timestamp" in df.columns:
                df["duration"] = df["last"] - df["timestamp"]
            else:
                df["duration"] = 0.0

        # Enforce duration is non-negative
        if "duration" in df.columns:
            df["duration"] = df["duration"].clip(lower=0.0)

        raw_records = df.to_dict(orient="records")
        return Normalizer.normalize_traffic(raw_records)
