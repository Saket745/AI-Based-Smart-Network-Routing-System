"""Classical routing algorithms module for nroute."""

from __future__ import annotations

import inspect
from typing import Any

from nroute.routing.ai import AIRouter
from nroute.routing.base import BaseRouter, FallbackRouter
from nroute.routing.base_nn import BaseNNRouter
from nroute.routing.bellman_ford import BellmanFordRouter
from nroute.routing.bfs import BFSRouter
from nroute.routing.dijkstra import DijkstraRouter
from nroute.routing.ecmp import ECMPRouter
from nroute.routing.negotiation import NegotiationRouter
from nroute.routing.registry import ROUTER_REGISTRY, register_router
from nroute.routing.rl_router import RLRouter


def _get_registered_router(alg: str, topology: Any = None) -> BaseRouter | None:
    """Check custom registry for a router and return an instance if found."""
    if alg in ROUTER_REGISTRY:
        router_cls = ROUTER_REGISTRY[alg]
        sig = inspect.signature(router_cls.__init__)
        if "topology" in sig.parameters:
            return router_cls(topology=topology)  # type: ignore[call-arg]
        return router_cls()
    return None


def _get_configured_router(
    alg: str, topology: Any = None, allow_unsafe: bool = False
) -> BaseRouter | None:
    """Check custom configuration registry for a router and return an instance if found."""
    from nroute.core.config import load_config
    from nroute.utils.loader import load_custom_class

    try:
        cfg = load_config()
        if alg in cfg.custom_routers:
            import_str = cfg.custom_routers[alg]
            router_cls = load_custom_class(
                import_str, expected_superclass=BaseRouter, allow_unsafe=allow_unsafe
            )
            sig = inspect.signature(router_cls.__init__)
            if "topology" in sig.parameters:
                return router_cls(topology=topology)  # type: ignore[call-arg]
            return router_cls()
    except Exception:
        pass
    return None


def _get_standard_router(alg: str, topology: Any = None) -> BaseRouter | None:
    """Check built-in standard routers and return an instance if found."""
    if alg == "dijkstra":
        return DijkstraRouter()
    elif alg in {"bellman-ford", "bellmanford"}:
        return BellmanFordRouter()
    elif alg == "ecmp":
        return ECMPRouter()
    elif alg == "ai":
        return AIRouter(topology=topology)
    elif alg == "bfs":
        return BFSRouter()
    elif alg in {"rl", "ppo", "dqn"}:
        rl_algo = "ppo" if alg == "rl" else alg
        return RLRouter(topology=topology, algorithm=rl_algo)
    elif alg == "negotiation":
        return NegotiationRouter(profile="balanced")
    elif alg == "negotiation-latency":
        return NegotiationRouter(profile="latency")
    elif alg == "negotiation-congestion":
        return NegotiationRouter(profile="congestion")
    elif alg == "negotiation-balanced":
        return NegotiationRouter(profile="balanced")
    return None


def get_router(algorithm: str, topology: Any = None, allow_unsafe: bool = False) -> BaseRouter:
    """
    Factory function to get a router instance by name.

    Args:
        algorithm: "dijkstra" | "bellman-ford" | "ecmp" | "bfs" | "ai" | "rl" | "ppo" | "dqn" or custom registered name.
        topology: Optional topology context.
        allow_unsafe: Whether to allow loading custom classes from local files (if configured).
    """
    alg = algorithm.lower().strip()

    router = _get_registered_router(alg, topology)
    if router is not None:
        return router

    router = _get_configured_router(alg, topology, allow_unsafe)
    if router is not None:
        return router

    router = _get_standard_router(alg, topology)
    if router is not None:
        return router

    raise ValueError(f"Unknown router name '{algorithm}'.")


__all__ = [
    "ROUTER_REGISTRY",
    "AIRouter",
    "BFSRouter",
    "BaseNNRouter",
    "BaseRouter",
    "BellmanFordRouter",
    "DijkstraRouter",
    "ECMPRouter",
    "FallbackRouter",
    "NegotiationRouter",
    "RLRouter",
    "get_router",
    "register_router",
]
