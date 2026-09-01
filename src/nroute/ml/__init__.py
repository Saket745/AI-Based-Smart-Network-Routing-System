"""AI/ML Module containing feature engineering, congestion prediction, and anomaly detection."""

from __future__ import annotations

from typing import Any

from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor
from nroute.ml.feature_eng import (
    create_congestion_labels,
    extract_anomaly_features,
    extract_congestion_features,
)
from nroute.ml.features import (
    BaseFeatureExtractor,
    DefaultGraphFeatureExtractor,
    GraphTensorBundle,
)
from nroute.ml.features.builder import FeatureBuilder
from nroute.ml.model_store import ModelStore


def __getattr__(name: str) -> Any:
    if name == "NetworkRoutingEnv":
        from nroute.ml.rl_env import NetworkRoutingEnv

        return NetworkRoutingEnv
    if name == "DatasetGenerator":
        from nroute.ml.datasets.generator import DatasetGenerator

        return DatasetGenerator
    if name == "GNNEvaluator":
        from nroute.ml.evaluation.metrics import GNNEvaluator

        return GNNEvaluator
    if name == "GCNModel":
        from nroute.ml.models.gcn import GCNModel

        return GCNModel
    if name == "GraphSAGEModel":
        from nroute.ml.models.graphsage import GraphSAGEModel

        return GraphSAGEModel
    if name == "GNNTrainer":
        from nroute.ml.training.trainer import GNNTrainer

        return GNNTrainer
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "AnomalyDetector",
    "BaseFeatureExtractor",
    "CongestionPredictor",
    "DatasetGenerator",
    "DefaultGraphFeatureExtractor",
    "FeatureBuilder",
    "GCNModel",
    "GNNEvaluator",
    "GNNTrainer",
    "GraphSAGEModel",
    "GraphTensorBundle",
    "ModelStore",
    "NetworkRoutingEnv",
    "create_congestion_labels",
    "extract_anomaly_features",
    "extract_congestion_features",
]
