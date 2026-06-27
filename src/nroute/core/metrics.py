"""Metrics models for routes and simulation results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from nroute.core.topology import Topology

from nroute.exceptions import SimulationError


class RouteMetrics(BaseModel):
    """
    Performance metrics computed for a specific route path.
    """

    path: list[str] = Field(
        ..., description="Ordered list of node IDs forming the route path"
    )
    total_latency: float = Field(
        ..., ge=0.0, description="Sum of propagation and queuing delays in ms"
    )
    total_hops: int = Field(
        ..., ge=0, description="Total number of edge hops (len(path) - 1)"
    )
    bottleneck_bandwidth: float = Field(
        ..., ge=0.0, description="Minimum link capacity along the path in Mbps"
    )
    bottleneck_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Maximum link utilization along the path"
    )

    @classmethod
    def from_path(cls, topology: Topology, path: list[str]) -> RouteMetrics:
        """
        Compute RouteMetrics for a given path and topology.
        """
        total_latency = 0.0
        total_hops = len(path) - 1
        bottleneck_bw = float("inf")
        bottleneck_util = 0.0

        for i in range(total_hops):
            u, v = path[i], path[i + 1]
            try:
                edge = topology.get_edge(u, v)
                total_latency += float(edge.get("latency", 0.0))
                bw = float(edge.get("bandwidth", float("inf")))
                util = float(edge.get("utilization", 0.0))
                if bw < bottleneck_bw:
                    bottleneck_bw = bw
                    bottleneck_util = util
            except Exception:
                pass

        return cls(
            path=path,
            total_latency=total_latency,
            total_hops=total_hops,
            bottleneck_bandwidth=bottleneck_bw,
            bottleneck_utilization=bottleneck_util,
        )


class SimulationMetrics(BaseModel):
    """
    Network-wide performance metrics recorded for a single simulation tick.
    """

    tick: int = Field(..., ge=0, description="Simulation tick index")
    timestamp: float = Field(..., ge=0.0, description="Simulation timestamp in seconds")
    throughput: float = Field(
        ..., ge=0.0, description="Aggregated network throughput in Mbps"
    )
    avg_latency: float = Field(
        ..., ge=0.0, description="Network-wide average flow latency in ms"
    )
    packet_loss_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of packets dropped"
    )
    avg_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Average utilization across active links"
    )
    reroute_count: int = Field(
        ..., ge=0, description="Number of flow rerouting events in this tick"
    )
    active_flows: int = Field(
        ..., ge=0, description="Number of active flows in this tick"
    )


class MetricsCollectionResult(BaseModel):
    """
    Collection of per-tick simulation metrics with analysis helpers.
    """

    results: list[SimulationMetrics] = Field(
        default_factory=list, description="Chronological simulation metrics"
    )

    def mean_latency(self) -> float:
        """
        Calculate the mean average latency across all simulation ticks.
        """
        if not self.results:
            return 0.0
        return sum(m.avg_latency for m in self.results) / len(self.results)

    def total_throughput(self) -> float:
        """
        Calculate the total summed throughput rate across all ticks.
        """
        return sum(m.throughput for m in self.results)

    def mean_throughput(self) -> float:
        """
        Calculate the mean throughput rate across all simulation ticks.
        """
        if not self.results:
            return 0.0
        return sum(m.throughput for m in self.results) / len(self.results)

    def peak_utilization(self) -> float:
        """
        Get the maximum average link utilization observed across all ticks.
        """
        if not self.results:
            return 0.0
        return max(m.avg_utilization for m in self.results)

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the metrics collection to a pandas DataFrame.
        """
        if not self.results:
            return pd.DataFrame(
                columns=[
                    "tick",
                    "timestamp",
                    "throughput",
                    "avg_latency",
                    "packet_loss_rate",
                    "avg_utilization",
                    "reroute_count",
                    "active_flows",
                ]
            )
        return pd.DataFrame([m.model_dump() for m in self.results])

    def to_json(self, path: str | Path) -> None:
        """
        Export simulation metrics to a JSON file.
        """
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump([m.model_dump() for m in self.results], f, indent=2)
        except Exception as e:
            raise SimulationError(
                f"Failed to export metrics to JSON {path}: {e}"
            ) from e

    def to_csv(self, path: str | Path) -> None:
        """
        Export simulation metrics to a CSV file.
        """
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            self.to_dataframe().to_csv(p, index=False)
        except Exception as e:
            raise SimulationError(f"Failed to export metrics to CSV {path}: {e}") from e
