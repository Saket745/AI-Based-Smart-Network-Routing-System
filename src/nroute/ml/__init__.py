"""AI/ML Module containing feature engineering, congestion prediction, and anomaly detection."""

from __future__ import annotations

from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor
from nroute.ml.datasets.generator import DatasetGenerator
from nroute.ml.evaluation.metrics import GNNEvaluator
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
from nroute.ml.models.gcn import GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel
from nroute.ml.rl_env import NetworkRoutingEnv
from nroute.ml.training.trainer import GNNTrainer

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
