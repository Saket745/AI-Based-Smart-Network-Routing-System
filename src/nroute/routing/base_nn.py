"""Base class for neural network and GNN-based routing strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from nroute.exceptions import RoutingError
from nroute.routing.base import BaseRouter

if TYPE_CHECKING:
    from nroute.core.topology import Topology
    from nroute.ml.features import BaseFeatureExtractor


class BaseNNRouter(BaseRouter, ABC):
    """
    Abstract base class for all neural network and GNN-based routing algorithms.

    Handles feature extraction, path validation, and step-by-step next-hop loop execution,
    allowing developers to focus solely on model architecture and prediction logic.
    """

    def __init__(
        self,
        model: Any = None,
        feature_extractor: BaseFeatureExtractor | None = None,
        topology: Topology | None = None,
    ) -> None:
        """
        Initialize the BaseNNRouter.

        Args:
            model: The custom neural network/ML model instance.
            feature_extractor: The feature extractor to use. If None, developers
                can manually build features inside predict_next_hop.
            topology: Optional topology context.
            confidence_threshold: Minimum confidence threshold.
        """
        self.model = model
        self.feature_extractor = feature_extractor
        self.topology = topology

    @abstractmethod
    def predict_next_hop(
        self,
        features: Any,
        current_node: str,
        destination: str,
        topology: Topology,
    ) -> str:
        """
        Predict the next hop node ID from current_node to destination.

        Args:
            features: Extracted features from the topology (via self.feature_extractor).
            current_node: Current node ID.
            destination: Target destination node ID.
            topology: The network topology.

        Returns:
            The predicted next hop node ID.
        """
        raise NotImplementedError

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: Any = None,
    ) -> list[str]:
        # Get active subgraph
        subgraph = self._get_active_subgraph(topology)

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist in topology.")
        if destination not in subgraph:
            raise RoutingError(
                f"Destination node '{destination}' is down or does not exist in topology."
            )

        if source == destination:
            return [source]

        # Extract features if extractor is available
        features = None
        if self.feature_extractor is not None:
            features = self.feature_extractor.extract_features(topology)

        path = [source]
        visited = {source}
        current = source
        max_hops = len(topology.nodes) * 2

        while current != destination:
            if len(path) > max_hops:
                raise RoutingError(
                    f"NN routing path exceeded maximum hop limit of {max_hops} (loop suspected)."
                )

            try:
                next_node = self.predict_next_hop(features, current, destination, topology)
            except Exception as e:
                raise RoutingError(f"NN router next-hop prediction failed: {e}") from e

            # Verify physical connectivity
            if next_node not in subgraph.neighbors(current):
                raise RoutingError(
                    f"NN router predicted invalid next-hop '{next_node}' from '{current}'. "
                    f"Link is either down, nonexistent, or disconnected."
                )

            # Loop detection
            if next_node in visited:
                raise RoutingError(
                    f"NN router predicted next-hop '{next_node}' causing a loop. Path: {path}"
                )

            path.append(next_node)
            visited.add(next_node)
            current = next_node

        self.validate_path(topology, path, source, destination)
        return path
