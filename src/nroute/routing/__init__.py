"""Classical routing algorithms module for nroute."""

from __future__ import annotations

from nroute.routing.base import BaseRouter, FallbackRouter
from nroute.routing.bellman_ford import BellmanFordRouter
from nroute.routing.dijkstra import DijkstraRouter
from nroute.routing.ecmp import ECMPRouter

__all__ = [
    "BaseRouter",
    "BellmanFordRouter",
    "DijkstraRouter",
    "ECMPRouter",
    "FallbackRouter",
]
