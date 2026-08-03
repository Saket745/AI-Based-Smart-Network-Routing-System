"""Core data structures and configurations for nroute."""

from __future__ import annotations

from nroute.core.config import NRouteConfig, load_config
from nroute.core.metrics import MetricsCollectionResult, RouteMetrics, SimulationMetrics
from nroute.core.topology import Topology
from nroute.core.traffic import FlowRecord, TrafficMatrix

__all__ = [
    "FlowRecord",
    "MetricsCollectionResult",
    "NRouteConfig",
    "RouteMetrics",
    "SimulationMetrics",
    "Topology",
    "TrafficMatrix",
    "load_config",
]
