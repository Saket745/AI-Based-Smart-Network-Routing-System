# AI-Based Smart Network Routing System (nroute)
# ──────────────────────────────────────────────────
# Public API — populated incrementally as modules are built.

"""
nroute — AI-Based Smart Network Routing System.
"""

from __future__ import annotations

from typing import Any

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
from nroute.routing import BaseRouter, get_router, register_router


class Simulator:
    """Facade class for simplifying simulation execution."""

    def __init__(self, topology: Any, algorithm: Any, duration: int) -> None:
        from nroute.simulation.engine import SimulationEngine
        from nroute.simulation.traffic_gen import TrafficGenerator

        self.topology = topology
        self.duration = duration

        if isinstance(algorithm, str):
            self.router = get_router(algorithm, topology=topology)
        else:
            self.router = algorithm

        # Default traffic generator
        self.traffic_generator = TrafficGenerator(model="uniform", n_flows_per_tick=3)
        self.engine = SimulationEngine(
            topology=self.topology,
            router=self.router,
            traffic_generator=self.traffic_generator,
        )

    def run(self, seed: int | None = None) -> Any:
        return self.engine.run(duration_ticks=self.duration, seed=seed)


__all__ = [
    "BaseRouter",
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
    "Simulator",
    "Topology",
    "TopologyError",
    "TrafficMatrix",
    "ValidationError",
    "__version__",
    "get_router",
    "load_config",
    "register_router",
]
