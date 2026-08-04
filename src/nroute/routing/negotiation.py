"""Multi-agent negotiation-based routing implementation using Contract Net Protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import networkx as nx

from nroute.exceptions import RoutingError
from nroute.routing.base import BaseRouter
from nroute.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.core.topology import Topology


@dataclass(frozen=True)
class NegotiationContext:
    """Context for hop-by-hop negotiation."""

    subgraph: nx.DiGraph
    destination: str
    weight_func: Callable[[str, str, dict[str, Any]], float] | None = None


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

    def _resolve_edge_weight(self, u: str, v: str, edge_data: dict[str, Any]) -> float:
        """Resolve edge weight based on the selected negotiation profile."""
        latency = float(edge_data.get("latency", 5.0))
        utilization = float(edge_data.get("utilization", 0.0))
        packet_loss = float(edge_data.get("packet_loss", 0.0))

        if self.profile == "latency":
            return latency
        if self.profile == "congestion":
            return latency / max(0.01, 1.0 - utilization)
        # balanced
        return latency + 50.0 * packet_loss + 5.0 / max(0.01, 1.0 - utilization)

    def _calculate_local_link_cost(
        self,
        u: str,
        v: str,
        edge_data: dict[str, Any],
        weight_func: Callable[[str, str, dict[str, Any]], float] | None,
    ) -> float:
        """Calculate local link cost between u and v."""
        if weight_func is not None:
            return weight_func(u, v, edge_data)
        return self._resolve_edge_weight(u, v, edge_data)

    def _calculate_remaining_cost(
        self,
        v: str,
        context: NegotiationContext,
    ) -> float | None:
        """
        Estimate remaining cost from v to the destination.

        Returns:
            The remaining cost as a float, or None if no path exists.
        """
        if v == context.destination:
            return 0.0

        rem_weight = context.weight_func or self._resolve_edge_weight

        try:
            return float(
                nx.shortest_path_length(
                    context.subgraph,
                    source=v,
                    target=context.destination,
                    weight=rem_weight,
                )
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def _calculate_bid(
        self,
        u: str,
        v: str,
        context: NegotiationContext,
    ) -> float | None:
        """
        Calculate the bid cost from neighbor v to reach the destination via link u -> v.

        Args:
            u: Current node.
            v: Neighbor node.
            context: The negotiation context.

        Returns:
            The bid cost as a float, or None if the neighbor cannot reach the destination.
        """
        # Calculate local link cost u -> v
        edge_data = context.subgraph.edges[u, v]
        link_cost = self._calculate_local_link_cost(u, v, edge_data, context.weight_func)

        # Estimate remaining cost from v to destination
        remaining_cost = self._calculate_remaining_cost(v, context)
        if remaining_cost is None:
            return None

        return link_cost + remaining_cost

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
        context = NegotiationContext(
            subgraph=subgraph,
            destination=destination,
            weight_func=weight_func,
        )

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

                bid_cost = self._calculate_bid(current_node, neighbor, context)
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
