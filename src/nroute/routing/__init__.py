"""Classical routing algorithms module for nroute."""

from __future__ import annotations

from typing import Any

from nroute.routing.ai import AIRouter
from nroute.routing.base import BaseRouter, FallbackRouter
from nroute.routing.bellman_ford import BellmanFordRouter
from nroute.routing.dijkstra import DijkstraRouter
from nroute.routing.ecmp import ECMPRouter
from nroute.routing.rl_router import RLRouter


def get_router(algorithm: str, topology: Any = None) -> BaseRouter:
    """
    Factory function to get a router instance by name.

    Args:
        algorithm: "dijkstra" | "bellman-ford" | "ecmp" | "ai" | "rl" | "ppo" | "dqn".
        topology: Optional topology context.
    """
    alg = algorithm.lower().strip()
    if alg == "dijkstra":
        return DijkstraRouter()
    elif alg in {"bellman-ford", "bellmanford"}:
        return BellmanFordRouter()
    elif alg == "ecmp":
        return ECMPRouter()
    elif alg == "ai":
        return AIRouter(topology=topology)
    elif alg in {"rl", "ppo", "dqn"}:
        rl_algo = "ppo" if alg == "rl" else alg
        return RLRouter(topology=topology, algorithm=rl_algo)
    else:
        raise ValueError(f"Unknown router name '{algorithm}'.")


__all__ = [
    "AIRouter",
    "BaseRouter",
    "BellmanFordRouter",
    "DijkstraRouter",
    "ECMPRouter",
    "FallbackRouter",
    "RLRouter",
    "get_router",
]
