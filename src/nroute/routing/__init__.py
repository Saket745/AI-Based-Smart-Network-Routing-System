"""Classical routing algorithms module for nroute."""

from __future__ import annotations

import inspect
from typing import Any

from nroute.routing.ai import AIRouter
from nroute.routing.base import BaseRouter, FallbackRouter
from nroute.routing.bellman_ford import BellmanFordRouter
from nroute.routing.bfs import BFSRouter
from nroute.routing.dijkstra import DijkstraRouter
from nroute.routing.ecmp import ECMPRouter
from nroute.routing.registry import ROUTER_REGISTRY, register_router
from nroute.routing.rl_router import RLRouter
from nroute.routing.negotiation import NegotiationRouter


def get_router(algorithm: str, topology: Any = None) -> BaseRouter:
    """
    Factory function to get a router instance by name.

    Args:
        algorithm: "dijkstra" | "bellman-ford" | "ecmp" | "bfs" | "ai" | "rl" | "ppo" | "dqn" or custom registered name.
        topology: Optional topology context.
    """
    alg = algorithm.lower().strip()

    # Check custom registry first
    if alg in ROUTER_REGISTRY:
        router_cls = ROUTER_REGISTRY[alg]
        sig = inspect.signature(router_cls.__init__)
        if "topology" in sig.parameters:
            return router_cls(topology=topology)  # type: ignore[call-arg]
        return router_cls()

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
    else:
        raise ValueError(f"Unknown router name '{algorithm}'.")


__all__ = [
    "ROUTER_REGISTRY",
    "AIRouter",
    "BFSRouter",
    "BaseRouter",
    "BellmanFordRouter",
    "DijkstraRouter",
    "ECMPRouter",
    "FallbackRouter",
    "RLRouter",
    "NegotiationRouter",
    "get_router",
    "register_router",
]
