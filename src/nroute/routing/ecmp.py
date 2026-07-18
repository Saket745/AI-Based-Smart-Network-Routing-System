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

    def _resolve_query_params(
        self,
        query: RoutingQuery | None,
        source: str | None,
        destination: str | None,
        weight: str | Callable[[dict[str, Any]], float] | None,
        k: int | None = None,
    ) -> tuple[str, str, str | Callable[[dict[str, Any]], float] | None, int]:
        """
        Resolve standard and backward-compatible query parameters.
        """
        if query is not None:
            k_val = query.k if query.k is not None else self.k
            return query.source, query.destination, query.weight, k_val
        if source is None or destination is None:
            raise ValueError("Either 'query' or ('source' and 'destination') must be provided.")
        k_val = k if k is not None else self.k
        return source, destination, weight, k_val

    def _get_validated_active_subgraph(
        self, topology: Topology, source: str, destination: str
    ) -> nx.DiGraph:
        """
        Get active subgraph and validate that source and destination are present and up.
        """
        subgraph = self._get_active_subgraph(topology)

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist.")
        if destination not in subgraph:
            raise RoutingError(f"Destination node '{destination}' is down or does not exist.")

        return subgraph

    def _resolve_weight_function(
        self, weight: str | Callable[[dict[str, Any]], float] | None
    ) -> Callable[[str, str, dict[str, Any]], float]:
        """
        Adapt weight attribute or callable into a standard NetworkX weight function.
        """
        if weight is None:
            def weight_func(u: str, v: str, d: dict[str, Any]) -> float:
                return float(d.get("weight", 1.0))
            return weight_func
        if isinstance(weight, str):
            weight_attr = weight
            def weight_func_attr(u: str, v: str, d: dict[str, Any]) -> float:
                return float(d.get(weight_attr, 1.0))
            return weight_func_attr
        wt_callable = weight
        def weight_func_callable(u: str, v: str, d: dict[str, Any]) -> float:
            return float(wt_callable(d))
        return weight_func_callable

    def compute_all_equal_cost_paths(
        self,
        topology: Topology,
        query: RoutingQuery | None = None,
        source: str | None = None,
        destination: str | None = None,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[list[str]]:
        """
        Find all shortest paths of equal minimum cost between source and destination.
        """
        source_val, dest_val, weight_val, _ = self._resolve_query_params(
            query, source, destination, weight
        )
        subgraph = self._get_validated_active_subgraph(topology, source_val, dest_val)
        weight_func = self._resolve_weight_function(weight_val)

        try:
            paths = nx.all_shortest_paths(
                subgraph,
                source=source_val,
                target=dest_val,
                weight=weight_func,
            )
            res_paths = [list(p) for p in paths]
            for p in res_paths:
                self.validate_path(topology, p, source_val, dest_val)
            return res_paths
        except nx.NetworkXNoPath as e:
            raise RoutingError(
                f"No active path found between '{source_val}' and '{dest_val}'."
            ) from e
        except Exception as e:
            if isinstance(e, RoutingError):
                raise
            raise RoutingError(f"ECMP equal cost path computation failed: {e}") from e

    def compute_k_shortest_paths(
        self,
        topology: Topology,
        query: RoutingQuery | None = None,
        source: str | None = None,
        destination: str | None = None,
        k: int | None = None,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[list[str]]:
        """
        Find the top K shortest simple paths using Yen's algorithm.
        """
        source_val, dest_val, weight_val, k_val = self._resolve_query_params(
            query, source, destination, weight, k
        )
        subgraph = self._get_validated_active_subgraph(topology, source_val, dest_val)
        weight_func = self._resolve_weight_function(weight_val)

        try:
            generator = nx.shortest_simple_paths(
                subgraph,
                source=source_val,
                target=dest_val,
                weight=weight_func,
            )
            paths = list(itertools.islice(generator, k_val))
            res_paths = [list(p) for p in paths]
            for p in res_paths:
                self.validate_path(topology, p, source_val, dest_val)
            return res_paths
        except (nx.NetworkXNoPath, StopIteration) as e:
            raise RoutingError(
                f"No active path found between '{source_val}' and '{dest_val}'."
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
        **kwargs: Any,
    ) -> list[str]:
        """
        Compute a single path. Uses ECMP (equal-cost paths) and selects one
        deterministically using the hash of flow_key.

        Args:
            topology: The network topology.
            source: Source node ID.
            destination: Destination node ID.
            weight: Routing metric.
            **kwargs: Additional parameters including 'flow_key'.
        """
        flow_key = kwargs.get("flow_key")
        query = RoutingQuery(
            source=source,
            destination=destination,
            weight=weight,
            flow_key=flow_key,
        )
        paths = self.compute_all_equal_cost_paths(topology, query)
        if not paths:
            raise RoutingError(f"No path found between '{source}' and '{destination}'.")

        # Select path using flow_key hashing
        if flow_key is not None:
            hash_val = int(hashlib.md5(str(flow_key).encode("utf-8")).hexdigest(), 16)
            index = hash_val % len(paths)
            return paths[index]

        # Default: return the first shortest path
        return paths[0]
