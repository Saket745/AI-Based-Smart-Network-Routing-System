"""Multi-agent negotiation-based routing implementation using Contract Net Protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

from nroute.exceptions import RoutingError
from nroute.routing.base import BaseRouter
from nroute.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.topology import Topology

logger = get_logger(__name__)


class NegotiationRouter(BaseRouter):
    """
    Router that simulates multi-agent routing negotiation using the Contract Net Protocol.
    Individual nodes act as autonomous agents, bidding on and forwarding traffic flows.
    """

    def __init__(self, profile: str = "balanced") -> None:
        """
        Initialize the NegotiationRouter.

        Args:
            profile: Negotiation profile for node agents: "latency" | "congestion" | "balanced"
        """
        self.profile = profile.lower().strip()
        if self.profile not in {"latency", "congestion", "balanced"}:
            raise ValueError(
                f"Unknown negotiation profile '{profile}'. Supported: latency, congestion, balanced."
            )

    def _calculate_bid(
        self,
        subgraph: nx.DiGraph,
        u: str,
        v: str,
        destination: str,
        weight_func: Callable[[str, str, dict[str, Any]], float] | None = None,
    ) -> float | None:
        """
        Calculate the bid cost from neighbor v to reach the destination via link u -> v.

        Args:
            subgraph: The active topology subgraph.
            u: Current node.
            v: Neighbor node.
            destination: Target destination node.
            weight_func: Optional weight override function.

        Returns:
            The bid cost as a float, or None if the neighbor cannot reach the destination.
        """
        # Calculate local link cost u -> v
        d = subgraph.edges[u, v]
        if weight_func is not None:
            link_cost = weight_func(u, v, d)
        else:
            latency = float(d.get("latency", 5.0))
            utilization = float(d.get("utilization", 0.0))
            packet_loss = float(d.get("packet_loss", 0.0))

            if self.profile == "latency":
                link_cost = latency
            elif self.profile == "congestion":
                # Avoid congestion: scale latency by remaining capacity
                link_cost = latency / max(0.01, 1.0 - utilization)
            else:  # balanced
                # Hybrid of latency, packet loss, and congestion penalty
                link_cost = (
                    latency
                    + 50.0 * packet_loss
                    + 5.0 / max(0.01, 1.0 - utilization)
                )

        # Estimate remaining cost from v to destination
        if v == destination:
            remaining_cost = 0.0
        else:
            try:
                if weight_func is not None:
                    rem_weight = weight_func
                else:
                    def rem_weight(x: str, y: str, edge_data: dict[str, Any]) -> float:
                        lat = float(edge_data.get("latency", 5.0))
                        util = float(edge_data.get("utilization", 0.0))
                        loss = float(edge_data.get("packet_loss", 0.0))
                        if self.profile == "latency":
                            return lat
                        elif self.profile == "congestion":
                            return lat / max(0.01, 1.0 - util)
                        else:
                            return lat + 50.0 * loss + 5.0 / max(0.01, 1.0 - util)

                remaining_cost = nx.shortest_path_length(
                    subgraph,
                    source=v,
                    target=destination,
                    weight=rem_weight,
                )
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return None

        return link_cost + remaining_cost

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[str]:
        # Get active subgraph (excluding down nodes and links)
        subgraph = self._get_active_subgraph(topology)

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist in topology.")
        if destination not in subgraph:
            raise RoutingError(
                f"Destination node '{destination}' is down or does not exist in topology."
            )

        if source == destination:
            return [source]

        # Adapt weight to NetworkX signature (u, v, data_dict) -> weight_value
        weight_func = None
        if weight is not None:
            if isinstance(weight, str):
                weight_attr = weight
                def weight_func_str(u: str, v: str, d: dict[str, Any]) -> float:
                    return float(d.get(weight_attr, 1.0))
                weight_func = weight_func_str
            else:
                wt_callable = weight
                def weight_func_callable(u: str, v: str, d: dict[str, Any]) -> float:
                    return float(wt_callable(d))
                weight_func = weight_func_callable

        # Hop-by-hop contract-net negotiation with backtracking
        def negotiate_path(
            current_node: str,
            path_so_far: list[str],
        ) -> list[str] | None:
            if current_node == destination:
                return path_so_far

            # Solicit bids from neighbors of current_node
            bids = []
            for neighbor in subgraph.neighbors(current_node):
                if neighbor in path_so_far:
                    # Loop prevention
                    continue

                bid_cost = self._calculate_bid(
                    subgraph, current_node, neighbor, destination, weight_func
                )
                if bid_cost is not None:
                    bids.append((neighbor, bid_cost))

            # Sort neighbors by bid cost (lowest first)
            bids.sort(key=lambda x: x[1])

            for neighbor, _ in bids:
                result = negotiate_path(neighbor, [*path_so_far, neighbor])
                if result is not None:
                    return result

            return None

        path = negotiate_path(source, [source])
        if path is None:
            raise RoutingError(
                f"Multi-agent negotiation failed to find a path from '{source}' to '{destination}'."
            )

        self.validate_path(topology, path, source, destination)
        return path
