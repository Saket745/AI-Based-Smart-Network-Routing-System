# AI-Based Smart Network Routing System (nroute)
# ──────────────────────────────────────────────────
# Public API — populated incrementally as modules are built.

"""
nroute — AI-Based Smart Network Routing System.
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Saket"
__license__ = "MIT"

# ── Public API (populated as phases are built) ─────────
from nroute.core import (
    FlowRecord,
    MetricsCollectionResult,
    NRouteConfig,
    RouteMetrics,
    SimulationMetrics,
    Topology,
    TrafficMatrix,
    load_config,
)
from nroute.exceptions import (
    ConfigError,
    IngestionError,
    ModelError,
    NRouteError,
    RoutingError,
    SimulationError,
    TopologyError,
    ValidationError,
)

__all__ = [
    "ConfigError",
    "FlowRecord",
    "IngestionError",
    "MetricsCollectionResult",
    "ModelError",
    "NRouteConfig",
    "NRouteError",
    "RouteMetrics",
    "RoutingError",
    "SimulationError",
    "SimulationMetrics",
    "Topology",
    "TopologyError",
    "TrafficMatrix",
    "ValidationError",
    "__version__",
    "load_config",
]
