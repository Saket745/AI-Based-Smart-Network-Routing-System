# AI-Based Smart Network Routing System (nroute)
# ──────────────────────────────────────────────────
# Production-grade CLI/library tool that uses AI/ML to
# simulate, visualize, and optimize network routing.
#
# Public API — populated incrementally as modules are built.

"""
nroute — AI-Based Smart Network Routing System.

A production-grade Python library and CLI tool for simulating,
visualizing, and optimizing network routing using AI/ML.

Supports congestion prediction, anomaly detection, and intelligent
path rerouting on both synthetic and real-world topologies.
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
from nroute.ml.rl_env import NetworkRoutingEnv
from nroute.routing import ROUTER_REGISTRY, AIRouter, BaseRouter, RLRouter, register_router


class Simulator:
    """
    Convenience facade class for running network simulations.
    Matches the PRD and Quickstart API signature.
    """

    def __init__(self, topology: Topology, algorithm: Any, duration: int) -> None:
        from nroute.simulation.engine import SimulationEngine
        from nroute.simulation.traffic_gen import TrafficGenerator

        self.topology = topology
        self.algorithm = algorithm
        self.duration = duration

        # Default to a uniform traffic generator with 5 flows per tick
        self.traffic_gen = TrafficGenerator(model="uniform", n_flows_per_tick=5)
        self.engine = SimulationEngine(topology, algorithm, self.traffic_gen)

    def run(self, seed: int | None = None) -> MetricsCollectionResult:
        """Run the simulation for the configured duration."""
        return self.engine.run(duration_ticks=self.duration, seed=seed)


__all__ = [
    "ROUTER_REGISTRY",
    "AIRouter",
    "BaseRouter",
    "ConfigError",
    "FlowRecord",
    "IngestionError",
    "MetricsCollectionResult",
    "ModelError",
    "NRouteConfig",
    "NRouteError",
    "NetworkRoutingEnv",
    "RLRouter",
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
    "load_config",
    "register_router",
]
