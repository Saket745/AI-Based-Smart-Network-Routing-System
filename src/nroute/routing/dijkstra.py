"""Dijkstra's shortest path routing implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

from nroute.exceptions import RoutingError
from nroute.routing.base import BaseRouter

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.topology import Topology


class DijkstraRouter(BaseRouter):
    """Router implementing Dijkstra's shortest path algorithm."""

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        # Get active subgraph (excluding down nodes and links)
        subgraph = self._get_active_subgraph(topology)

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist in topology.")
        if destination not in subgraph:
            raise RoutingError(
                f"Destination node '{destination}' is down or does not exist in topology."
            )

        # Adapt weight for NetworkX. Passing string attribute directly allows
        # fast internal C/dict lookups in NetworkX shortest path algorithms.
        nx_weight: str | Callable[[str, str, dict[str, Any]], float]
        if weight is None or isinstance(weight, str):
            nx_weight = weight or "weight"
        else:
            wt_callable = weight

            def weight_func(u: str, v: str, d: dict[str, Any]) -> float:
                return float(wt_callable(d))

            nx_weight = weight_func

        try:
            path = nx.shortest_path(
                subgraph,
                source=source,
                target=destination,
                weight=nx_weight,
            )
            res_path = list(path)
            # Validate computed path (ensures active links and correct endpoints)
            self.validate_path(topology, res_path, source, destination)
            return res_path
        except nx.NetworkXNoPath as e:
            raise RoutingError(
                f"No active path found between '{source}' and '{destination}'."
            ) from e
        except Exception as e:
            if isinstance(e, RoutingError):
                raise
            raise RoutingError(f"Dijkstra route computation failed: {e}") from e
