"""Bellman-Ford shortest path routing implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

from nroute.exceptions import RoutingError
from nroute.routing.base import BaseRouter

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.topology import Topology


class BellmanFordRouter(BaseRouter):
    """Router implementing Bellman-Ford shortest path algorithm."""

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[str]:
        # Get active subgraph
        subgraph = self._get_active_subgraph(topology)

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist in topology.")
        if destination not in subgraph:
            raise RoutingError(
                f"Destination node '{destination}' is down or does not exist in topology."
            )

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
            path = nx.bellman_ford_path(
                subgraph,
                source=source,
                target=destination,
                weight=weight_func,
            )
            res_path = list(path)
            self.validate_path(topology, res_path, source, destination)
            return res_path
        except nx.NetworkXNoPath as e:
            raise RoutingError(
                f"No active path found between '{source}' and '{destination}'."
            ) from e
        except nx.NetworkXUnbounded as e:
            raise RoutingError(
                f"Bellman-Ford failed: negative weight cycle detected. Detail: {e}"
            ) from e
        except Exception as e:
            if isinstance(e, RoutingError):
                raise
            raise RoutingError(f"Bellman-Ford route computation failed: {e}") from e
