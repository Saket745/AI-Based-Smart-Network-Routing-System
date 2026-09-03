# NRoute — Network Digital Twin & Pre-Flight Change-Impact Validation Platform
# ─────────────────────────────────────────────────────────────────────────────
# High-performance network digital twin platform providing deterministic
# graph modeling, what-if change-impact simulation, and declarative policy gating.

"""
nroute — High-Performance Network Digital Twin & Pre-Flight Change-Impact Validation Platform.

Deterministic network simulation, change blast-radius evaluation, and
automated safety policy validation returning PASS/WARN/BLOCK verdicts.
"""

from __future__ import annotations

from typing import Any

__version__ = "1.3.0"
__author__ = "Saket"
__license__ = "MIT"

# ── Public API ─────────────────────────────────────────
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
from nroute.core.openconfig import ConfigChange
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
from nroute.routing import (
    ROUTER_REGISTRY,
    BaseRouter,
    get_router,
    register_router,
)
from nroute.simulation.change_impact import ChangeImpactSimulator
from nroute.simulation.digital_twin import DigitalTwinEngine
from nroute.simulation.policy import (
    PolicyGateConfig,
    ValidationResult,
    ValidationVerdict,
)
from nroute.simulation.validator import PreFlightValidator


def __getattr__(name: str) -> Any:
    if name in {"BaseFeatureExtractor", "DefaultGraphFeatureExtractor"}:
        from nroute.ml.features.extractor import (
            BaseFeatureExtractor,
            DefaultGraphFeatureExtractor,
        )

        return (
            BaseFeatureExtractor if name == "BaseFeatureExtractor" else DefaultGraphFeatureExtractor
        )
    if name == "GraphTensorBundle":
        from nroute.ml.graph.bundle import GraphTensorBundle

        return GraphTensorBundle
    if name == "NetworkRoutingEnv":
        from nroute.ml.rl_env import NetworkRoutingEnv

        return NetworkRoutingEnv
    if name == "RLRouter":
        from nroute.routing.rl_router import RLRouter

        return RLRouter
    if name == "AIRouter":
        from nroute.routing.ai import AIRouter

        return AIRouter
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


class Simulator:
    """
    Convenience facade class for running network simulations.
    Matches the PRD and Quickstart API signature.
    """

    def __init__(self, topology: Topology, algorithm: Any, duration: int) -> None:
        from nroute.routing import get_router
        from nroute.simulation.engine import SimulationEngine
        from nroute.simulation.traffic_gen import TrafficGenerator

        self.topology = topology
        self.algorithm = algorithm
        self.duration = duration

        # Resolve algorithm if passed as a string
        if isinstance(algorithm, str):
            self.router = get_router(algorithm, topology=topology)
        else:
            self.router = algorithm

        # Default to a uniform traffic generator with 5 flows per tick
        self.traffic_gen = TrafficGenerator(model="uniform", n_flows_per_tick=5)
        self.engine = SimulationEngine(topology, self.router, self.traffic_gen)

    def run(self, seed: int | None = None) -> MetricsCollectionResult:
        """Run the simulation for the configured duration."""
        return self.engine.run(duration_ticks=self.duration, seed=seed)


__all__ = [
    "ROUTER_REGISTRY",
    "AIRouter",
    "BaseFeatureExtractor",
    "BaseRouter",
    "ChangeImpactSimulator",
    "ConfigChange",
    "ConfigError",
    "DefaultGraphFeatureExtractor",
    "DigitalTwinEngine",
    "FlowRecord",
    "GraphTensorBundle",
    "IngestionError",
    "MetricsCollectionResult",
    "ModelError",
    "NRouteConfig",
    "NRouteError",
    "NetworkRoutingEnv",
    "PolicyGateConfig",
    "PreFlightValidator",
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
    "ValidationResult",
    "ValidationVerdict",
    "__version__",
    "get_router",
    "load_config",
    "register_router",
]
