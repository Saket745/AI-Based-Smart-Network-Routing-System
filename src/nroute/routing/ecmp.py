"""ECMP (Equal-Cost Multi-Path) and K-Shortest-Paths routing implementation."""

from __future__ import annotations

import hashlib
import itertools
from typing import TYPE_CHECKING, Any

import networkx as nx

from nroute.core.query import RoutingQuery
from nroute.exceptions import RoutingError
from nroute.routing.base import BaseRouter

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.topology import Topology


class ECMPRouter(BaseRouter):
    """
    Router implementing Equal-Cost Multi-Path (ECMP) and K-Shortest-Paths.
    """

    def __init__(self, k: int = 3) -> None:
        """
        Initialize the ECMPRouter.

        Args:
            k: Default number of paths to find when computing K-shortest paths.
        """
        self.k = k

    def compute_all_equal_cost_paths(
        self,
        topology: Topology,
        query: RoutingQuery,
    ) -> list[list[str]]:
        """
        Find all shortest paths of equal minimum cost between source and destination.
        """
        subgraph = self._get_active_subgraph(topology)
        source, destination = query.source, query.destination
        weight = query.weight

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist.")
        if destination not in subgraph:
            raise RoutingError(f"Destination node '{destination}' is down or does not exist.")

        # Adapt weight
        if weight is None:

            def weight_func(u: str, v: str, d: dict[str, Any]) -> float:
                return float(d.get("weight", 1.0))
        elif isinstance(weight, str):
            weight_attr = weight

            def weight_func(u: str, v: str, d: dict[str, Any]) -> float:
                return float(d.get(weight_attr, 1.0))
        else:
            wt_callable = weight

            def weight_func(u: str, v: str, d: dict[str, Any]) -> float:
                return float(wt_callable(d))

        try:
            paths = nx.all_shortest_paths(
                subgraph,
                source=source,
                target=destination,
                weight=weight_func,
            )
            res_paths = [list(p) for p in paths]
            for p in res_paths:
                self.validate_path(topology, p, source, destination)
            return res_paths
        except nx.NetworkXNoPath as e:
            raise RoutingError(
                f"No active path found between '{source}' and '{destination}'."
            ) from e
        except Exception as e:
            if isinstance(e, RoutingError):
                raise
            raise RoutingError(f"ECMP equal cost path computation failed: {e}") from e

    def compute_k_shortest_paths(
        self,
        topology: Topology,
        query: RoutingQuery,
    ) -> list[list[str]]:
        """
        Find the top K shortest simple paths using Yen's algorithm.
        """
        subgraph = self._get_active_subgraph(topology)
        k_val = query.k if query.k is not None else self.k
        source, destination = query.source, query.destination
        weight = query.weight

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist.")
        if destination not in subgraph:
            raise RoutingError(f"Destination node '{destination}' is down or does not exist.")

        # Adapt weight
        if weight is None:

            def weight_func(u: str, v: str, d: dict[str, Any]) -> float:
                return float(d.get("weight", 1.0))
        elif isinstance(weight, str):
            weight_attr = weight

            def weight_func(u: str, v: str, d: dict[str, Any]) -> float:
                return float(d.get(weight_attr, 1.0))
        else:
            wt_callable = weight

            def weight_func(u: str, v: str, d: dict[str, Any]) -> float:
                return float(wt_callable(d))

        try:
            generator = nx.shortest_simple_paths(
                subgraph,
                source=source,
                target=destination,
                weight=weight_func,
            )
            paths = list(itertools.islice(generator, k_val))
            res_paths = [list(p) for p in paths]
            for p in res_paths:
                self.validate_path(topology, p, source, destination)
            return res_paths
        except (nx.NetworkXNoPath, StopIteration) as e:
            raise RoutingError(
                f"No active path found between '{source}' and '{destination}'."
            ) from e
        except Exception as e:
            if isinstance(e, RoutingError):
                raise
            raise RoutingError(f"K-shortest path computation failed: {e}") from e

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
        flow_key: str | int | None = None,
    ) -> list[str]:
        """
        Compute a single path. Uses ECMP (equal-cost paths) and selects one
        deterministically using the hash of flow_key.

        Args:
            topology: The network topology.
            source: Source node ID.
            destination: Destination node ID.
            weight: Routing metric.
            flow_key: Key used to hash and select one of the equal-cost paths (e.g. protocol or flow ID).
        """
        query = RoutingQuery(
            source=source, destination=destination, weight=weight, flow_key=flow_key
        )
        paths = self.compute_all_equal_cost_paths(topology, query)
        if not paths:
            raise RoutingError(f"No path found between '{source}' and '{destination}'.")

        # Select path using flow_key hashing
        key = query.flow_key
        if key is not None:
            hash_val = int(hashlib.md5(str(key).encode("utf-8")).hexdigest(), 16)
            index = hash_val % len(paths)
            return paths[index]

        # Default: return the first shortest path
        return paths[0]
