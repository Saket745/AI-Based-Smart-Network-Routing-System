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


def _instantiate_router(router_cls: type[BaseRouter], topology: Any = None) -> BaseRouter:
    """Helper to instantiate a router class, passing topology if accepted."""
    sig = inspect.signature(router_cls.__init__)
    if "topology" in sig.parameters:
        return router_cls(topology=topology)  # type: ignore[call-arg]
    return router_cls()


def _get_registered_router(alg: str, topology: Any = None) -> BaseRouter | None:
    """Check custom registry for a router."""
    if alg in ROUTER_REGISTRY:
        return _instantiate_router(ROUTER_REGISTRY[alg], topology=topology)
    return None


def _get_config_custom_router(
    alg: str, topology: Any = None, allow_unsafe: bool = False
) -> BaseRouter | None:
    """Check custom configuration registry for a router."""
    from nroute.core.config import load_config
    from nroute.utils.loader import load_custom_class

    try:
        cfg = load_config()
        if alg in cfg.custom_routers:
            import_str = cfg.custom_routers[alg]
            router_cls = load_custom_class(
                import_str, expected_superclass=BaseRouter, allow_unsafe=allow_unsafe
            )
            return _instantiate_router(router_cls, topology=topology)
    except Exception:
        pass
    return None


def _get_builtin_router(alg: str, topology: Any = None) -> BaseRouter | None:
    """Get a built-in router instance by name."""
    if alg == "dijkstra":
        return DijkstraRouter()
    if alg in {"bellman-ford", "bellmanford"}:
        return BellmanFordRouter()
    if alg == "ecmp":
        return ECMPRouter()
    if alg == "ai":
        return AIRouter(topology=topology)
    if alg == "bfs":
        return BFSRouter()
    if alg in {"rl", "ppo", "dqn"}:
        rl_algo = "ppo" if alg == "rl" else alg
        return RLRouter(topology=topology, algorithm=rl_algo)
    if alg == "negotiation":
        return NegotiationRouter(profile="balanced")
    if alg == "negotiation-latency":
        return NegotiationRouter(profile="latency")
    if alg == "negotiation-congestion":
        return NegotiationRouter(profile="congestion")
    if alg == "negotiation-balanced":
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

    router = _get_registered_router(alg, topology=topology)
    if router is not None:
        return router

    router = _get_config_custom_router(alg, topology=topology, allow_unsafe=allow_unsafe)
    if router is not None:
        return router

    router = _get_builtin_router(alg, topology=topology)
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
