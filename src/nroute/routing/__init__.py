"""Classical routing algorithms module for nroute."""

from __future__ import annotations

from typing import Any

from nroute.routing.ai import AIRouter
from nroute.routing.base import BaseRouter, FallbackRouter
from nroute.routing.bellman_ford import BellmanFordRouter
from nroute.routing.dijkstra import DijkstraRouter
from nroute.routing.ecmp import ECMPRouter


def get_router(algorithm: str, topology: Any = None) -> BaseRouter:
    """
    Factory function to get a router instance by name.

    Args:
        algorithm: "dijkstra" | "bellman-ford" | "ecmp" | "ai" | "rl".
        topology: Optional topology context (needed for AIRouter).
    """
    alg = algorithm.lower().strip()
    if alg == "dijkstra":
        return DijkstraRouter()
    elif alg in {"bellman-ford", "bellmanford"}:
        return BellmanFordRouter()
    elif alg == "ecmp":
        return ECMPRouter()
    elif alg in {"ai", "rl"}:
        return AIRouter(topology=topology)
    else:
        raise ValueError(f"Unknown router name '{algorithm}'.")


__all__ = [
    "BaseRouter",
    "BellmanFordRouter",
    "DijkstraRouter",
    "ECMPRouter",
    "FallbackRouter",
    "AIRouter",
    "get_router",
]
