"""Abstract base class and fallback chaining for routing algorithms."""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import networkx as nx

from nroute.exceptions import RoutingError

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.topology import Topology
    from nroute.core.traffic import TrafficMatrix


class BaseRouter(ABC):
    """Abstract base class for all routing algorithms (classical & AI-based)."""

    @abstractmethod
    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """
        Compute a single path between source and destination nodes.

        Args:
            topology: The network topology.
            source: Source node ID.
            destination: Destination node ID.
            weight: Edge attribute name or weight function to use as routing metric.
            **kwargs: Additional routing parameters (algorithm-specific).

        Returns:
            A list of node IDs representing the path from source to destination.

        Raises:
            RoutingError: If no path exists or computation fails.
        """
        raise NotImplementedError

    def compute_routes(
        self,
        topology: Topology,
        traffic_matrix: TrafficMatrix,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
        **kwargs: Any,
    ) -> dict[tuple[str, str], list[str]]:
        """
        Compute paths for all flow records in a traffic matrix.

        Args:
            topology: The network topology.
            traffic_matrix: The traffic matrix containing flow demands.
            weight: Edge attribute name or weight function to use as routing metric.
            **kwargs: Additional routing parameters passed to compute_path.

        Returns:
            A dictionary mapping (source, destination) to the computed path.
        """
        routes = {}
        for flow in traffic_matrix.flows:
            pair = (flow.source, flow.destination)
            if pair in routes:
                continue
            try:
                path = self.compute_path(
                    topology, flow.source, flow.destination, weight=weight, **kwargs
                )
                routes[pair] = path
            except RoutingError:
                # Flow is unreachable on current topology configuration
                pass
        return routes

    def validate_path(
        self,
        topology: Topology,
        path: list[str],
        source: str | None = None,
        destination: str | None = None,
    ) -> bool:
        """
        Validate if a computed path is physically and logically valid.

        Args:
            topology: The network topology.
            path: List of node IDs representing the path.
            source: Expected source node ID (optional).
            destination: Expected destination node ID (optional).

        Returns:
            True if valid, raises RoutingError if invalid.
        """
        if not path:
            raise RoutingError("Path is empty.")

        if source is not None and path[0] != source:
            raise RoutingError(
                f"Path source '{path[0]}' does not match expected source '{source}'."
            )

        if destination is not None and path[-1] != destination:
            raise RoutingError(
                f"Path destination '{path[-1]}' does not match expected destination '{destination}'."
            )

        for node in path:
            if node not in topology.nodes:
                raise RoutingError(f"Node '{node}' in path does not exist in topology.")
            # If a node is down, the route is invalid
            if topology.get_node(node).get("status") == "down":
                raise RoutingError(f"Node '{node}' in path is down.")

        for u, v in itertools.pairwise(path):
            if (u, v) not in topology.edges:
                raise RoutingError(f"Edge '{u}->{v}' in path does not exist in topology.")
            edge_attr = topology.get_edge(u, v)
            if edge_attr.get("status") == "down":
                raise RoutingError(f"Edge '{u}->{v}' in path is down.")

        return True

    def _get_active_subgraph(self, topology: Topology) -> nx.DiGraph:
        """
        Get a read-only filtered view of the topology containing only active nodes and edges.
        """
        # Performance optimization: if no nodes or edges are down, return the graph directly.
        # This avoids the high overhead of nx.subgraph_view callbacks.
        has_down_nodes = any(d.get("status") == "down" for n, d in topology.graph.nodes(data=True))
        has_down_edges = any(
            d.get("status") == "down" for u, v, d in topology.graph.edges(data=True)
        )
        if not has_down_nodes and not has_down_edges:
            return topology.graph

        def filter_node(node: str) -> bool:
            return str(topology.get_node(node).get("status", "up")).lower() != "down"

        def filter_edge(u: str, v: str) -> bool:
            return str(topology.get_edge(u, v).get("status", "up")).lower() != "down"

        return nx.subgraph_view(
            topology.graph,
            filter_node=filter_node,
            filter_edge=filter_edge,
        )


class FallbackRouter(BaseRouter):
    """
    Chains multiple routers together.
    If the first router fails to find a path, it falls back to the next one in the list.
    """

    def __init__(self, routers: list[BaseRouter]) -> None:
        """
        Initialize the FallbackRouter with a list of sub-routers.
        """
        if not routers:
            raise ValueError("FallbackRouter requires at least one sub-router.")
        self.routers = routers

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        errors = []
        for router in self.routers:
            try:
                path = router.compute_path(topology, source, destination, weight=weight, **kwargs)
                # Ensure the path is valid before returning it
                self.validate_path(topology, path, source, destination)
                return path
            except RoutingError as e:
                errors.append(f"{router.__class__.__name__}: {e}")

        raise RoutingError(
            f"All routers in the fallback chain failed to find a path from '{source}' to '{destination}'. "
            f"Errors: {'; '.join(errors)}"
        )
