"""Dynamic Dijkstra routing algorithm evaluating real-time link utilization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nroute.routing.dijkstra import DijkstraRouter

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class DynamicDijkstraRouter(DijkstraRouter):
    """
    Shortest Path First router that dynamically penalizes congested links
    using instantaneous link utilization available on the topology graph at routing time.

    Weight function:
        W_e = Latency_e * (1.0 + alpha * Utilization_e)
    where alpha matches the base alpha used by AIRouter (default 5.0).
    """

    def __init__(self, alpha: float = 5.0) -> None:
        super().__init__()
        self.alpha = alpha

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: Any = None,
        **kwargs: Any,
    ) -> list[str]:
        """Compute shortest path with dynamic link utilization penalty."""
        alpha = self.alpha

        def dynamic_weight(d: dict[str, Any]) -> float:
            latency = float(d.get("latency", 5.0))
            utilization = float(d.get("utilization", 0.0))
            return latency * (1.0 + alpha * utilization)

        # Delegate to DijkstraRouter using our dynamic weight function
        return super().compute_path(
            topology=topology,
            source=source,
            destination=destination,
            weight=dynamic_weight,
            **kwargs,
        )
