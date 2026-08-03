"""BFS (Breadth-First Search) unweighted shortest path routing implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

from nroute.exceptions import RoutingError
from nroute.routing.base import BaseRouter

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.topology import Topology


class BFSRouter(BaseRouter):
    """Router implementing unweighted shortest path via BFS.

    Uses ``nx.shortest_path(G, source, target, weight=None)`` which
    performs a breadth-first search on the active subgraph, returning
    the path with the fewest hops regardless of link metrics.
    """

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[str]:
        """Compute the unweighted (minimum-hop) shortest path.

        Args:
            topology: The network topology.
            source: Source node ID.
            destination: Destination node ID.
            weight: Ignored — BFS always uses unweighted hop count.

        Returns:
            A list of node IDs representing the minimum-hop path.

        Raises:
            RoutingError: If no path exists between source and destination.
        """
        subgraph = self._get_active_subgraph(topology)

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist in topology.")
        if destination not in subgraph:
            raise RoutingError(
                f"Destination node '{destination}' is down or does not exist in topology."
            )

        try:
            path = nx.shortest_path(
                subgraph,
                source=source,
                target=destination,
                weight=None,  # Unweighted BFS
            )
            res_path = list(path)
            self.validate_path(topology, res_path, source, destination)
            return res_path
        except nx.NetworkXNoPath as e:
            raise RoutingError(
                f"No active path found between '{source}' and '{destination}' (BFS)."
            ) from e
        except Exception as e:
            if isinstance(e, RoutingError):
                raise
            raise RoutingError(f"BFS route computation failed: {e}") from e
