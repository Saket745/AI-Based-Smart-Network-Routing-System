"""AI-powered routing strategy using congestion prediction and anomaly detection."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import networkx as nx
import pandas as pd

from nroute.exceptions import RoutingError
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor
from nroute.ml.feature_eng import extract_anomaly_features, extract_congestion_features
from nroute.routing.base import BaseRouter
from nroute.utils.logging import get_logger

if TYPE_CHECKING:
    from nroute.core.topology import Topology
    from nroute.core.traffic import TrafficMatrix

logger = get_logger(__name__)


class AIRouter(BaseRouter):
    """
    AI-powered router that dynamically routes traffic around congestion
    by forecasting link utilization and detecting network anomalies.
    """

    def __init__(
        self,
        topology: Topology | None = None,
        congestion_model_type: str = "xgboost",
        anomaly_model_type: str = "isolation_forest",
        alpha: float = 5.0,
    ) -> None:
        """
        Initialize the AIRouter.

        Args:
            topology: Optional topology context.
            congestion_model_type: "xgboost" | "lstm".
            anomaly_model_type: "isolation_forest" | "autoencoder".
            alpha: Scale factor for congestion weight penalty (W_e = latency * (1 + alpha * prob)).
        """
        self.topology = topology
        self.alpha = alpha

        self.congestion_predictor = CongestionPredictor(model_type=congestion_model_type)
        self.anomaly_detector = AnomalyDetector(model_type=anomaly_model_type)
        self.is_trained = False

    def train(
        self,
        features_congestion: pd.DataFrame | None = None,
        labels_congestion: Any = None,
        features_anomaly: pd.DataFrame | None = None,
        epochs: int = 100,
    ) -> dict[str, Any]:
        """
        Train both congestion and anomaly models.

        Args:
            features_congestion: Congestion features DataFrame.
            labels_congestion: Congestion labels (0/1).
            features_anomaly: Anomaly normal traffic features DataFrame.
            epochs: Training epochs for neural models.

        Returns:
            Dictionary of training results and metrics.
        """
        results: dict[str, Any] = {}

        # 1. Train Congestion Predictor if features are provided
        if features_congestion is not None and labels_congestion is not None:
            logger.info("Training congestion prediction model...")
            results["congestion"] = self.congestion_predictor.train(
                features_congestion, labels_congestion, epochs=epochs
            )

        # 2. Train Anomaly Detector if normal features are provided
        if features_anomaly is not None:
            logger.info("Training anomaly detection model...")
            self.anomaly_detector.fit(features_anomaly, epochs=epochs)
            results["anomaly"] = {"status": "trained"}

        self.is_trained = self.congestion_predictor.is_trained or self.anomaly_detector.is_trained
        return results

    def predict_congestion(
        self, topology: Topology, traffic_history: list[TrafficMatrix]
    ) -> pd.DataFrame:
        """Extract features and predict link congestion probabilities."""
        features = extract_congestion_features(topology, traffic_history)
        return self.congestion_predictor.predict(features)

    def detect_anomalies(self, traffic: TrafficMatrix) -> pd.DataFrame:
        """Extract features and detect anomalies in traffic matrix."""
        features = extract_anomaly_features(traffic)
        return self.anomaly_detector.detect(features)

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> list[str]:
        """
        Compute path from source to destination routing around predicted congestion.

        Args:
            topology: The network topology.
            source: Source node ID.
            destination: Destination node ID.
            weight: Unused, kept to preserve BaseRouter method signature.
        """
        subgraph = self._get_active_subgraph(topology)

        if source not in subgraph:
            raise RoutingError(f"Source node '{source}' is down or does not exist.")
        if destination not in subgraph:
            raise RoutingError(f"Destination node '{destination}' is down or does not exist.")

        # If model is not trained, fallback to classical latency-based routing
        if not self.congestion_predictor.is_trained:
            logger.warning("AIRouter congestion model is not trained. Falling back to Dijkstra.")
            try:
                path = nx.shortest_path(
                    subgraph,
                    source=source,
                    target=destination,
                    weight=lambda u, v, d: float(d.get("latency", 5.0)),
                )
                res_path = list(path)
                self.validate_path(topology, res_path, source, destination)
                return res_path
            except nx.NetworkXNoPath as e:
                raise RoutingError(
                    f"No path found between '{source}' and '{destination}' (fallback)."
                ) from e

        # Extract features and predict congestion probabilities
        try:
            features = extract_congestion_features(topology, [])
            predictions = self.congestion_predictor.predict(features)
        except Exception as e:
            logger.error(
                "Failed to predict congestion in AIRouter. Falling back to Dijkstra.", error=str(e)
            )
            predictions = pd.DataFrame(columns=["probability"])

        # Compute dynamic edge weights: W_e = latency * (1.0 + alpha * congestion_prob)
        def dynamic_weight_func(u: str, v: str, d: dict[str, Any]) -> float:
            link_id = f"{u}->{v}"
            latency = float(d.get("latency", 5.0))

            prob = 0.0
            if link_id in predictions.index:
                prob = float(predictions.loc[link_id, "probability"])

            return latency * (1.0 + self.alpha * prob)

        try:
            path = nx.shortest_path(
                subgraph,
                source=source,
                target=destination,
                weight=dynamic_weight_func,
            )
            res_path = list(path)
            self.validate_path(topology, res_path, source, destination)
            return res_path
        except nx.NetworkXNoPath as e:
            raise RoutingError(
                f"No active path found between '{source}' and '{destination}' using AI weights."
            ) from e
        except Exception as e:
            if isinstance(e, RoutingError):
                raise
            raise RoutingError(f"AIRouter computation failed: {e}") from e

    def save(self, path: str) -> None:
        """Save predictor and detector models."""
        # Save models into prefix names
        self.congestion_predictor.save(f"{path}.congestion")
        self.anomaly_detector.save(f"{path}.anomaly")

    def load(self, path: str) -> None:
        """Load predictor and detector models."""
        self.congestion_predictor.load(f"{path}.congestion")
        self.anomaly_detector.load(f"{path}.anomaly")
        self.is_trained = self.congestion_predictor.is_trained or self.anomaly_detector.is_trained
