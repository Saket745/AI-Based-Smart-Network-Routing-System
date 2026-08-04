"""Anomaly detector model implementing Isolation Forest and PyTorch Autoencoders."""

from __future__ import annotations

import os
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.ensemble import IsolationForest
from torch.utils.data import DataLoader, TensorDataset

from nroute.exceptions import ModelError


class AutoencoderNet(nn.Module):
    """PyTorch Autoencoder network for anomaly detection."""

    def __init__(self, input_dim: int) -> None:
        super().__init__()
        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, max(4, input_dim // 2)),
            nn.ReLU(),
            nn.Linear(max(4, input_dim // 2), 2),
            nn.ReLU(),
        )
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(2, max(4, input_dim // 2)),
            nn.ReLU(),
            nn.Linear(max(4, input_dim // 2), input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        latent = self.encoder(x)
        reconstructed = self.decoder(latent)
        return cast("torch.Tensor", reconstructed)


class AnomalyDetector:
    """
    Detects network traffic anomalies (e.g., DDoS, link failure, black holes)
    using Isolation Forest or Autoencoder models.
    """

    @property
    def preferred_extension(self) -> str:
        """Get the preferred file extension for saving the model."""
        if self.model_type == "autoencoder":
            return ".pt"
        return ".joblib"

    def __init__(
        self,
        model_type: str = "isolation_forest",
        contamination: float = 0.05,
        custom_model: Any = None,
    ) -> None:
        """
        Initialize the AnomalyDetector.

        Args:
            model_type: "isolation_forest" | "autoencoder" | "custom".
            contamination: Fraction of outliers expected in training data (default 5%).
            custom_model: Optional custom model instance for "custom" type.
        """
        self.model_type = model_type.lower().strip()
        self.contamination = contamination
        self.model: Any = None
        self.is_trained = False

        # Threshold for reconstruction error (Autoencoder only)
        self.reconstruction_threshold = 0.0
        # Normalization parameters for training features
        self.feature_means: np.ndarray | None = None
        self.feature_stds: np.ndarray | None = None

        if self.model_type == "isolation_forest":
            self.model = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100,
            )
        elif self.model_type == "autoencoder":
            # Actual network is initialized during fit() when input dimension is known
            self.model = None
        elif self.model_type == "custom":
            if custom_model is None:
                raise ValueError("custom_model must be provided if model_type is 'custom'.")
            self.model = custom_model
            self.is_trained = getattr(custom_model, "is_trained", False)
        else:
            raise ValueError(
                f"Unknown model_type '{model_type}'. Supported: isolation_forest, autoencoder, custom."
            )

    def _normalize(self, x: np.ndarray, train: bool = False) -> np.ndarray:
        """Normalize features to zero mean and unit variance."""
        if train:
            self.feature_means = np.mean(x, axis=0)
            stds = np.std(x, axis=0)
            # Prevent division by zero
            stds[stds == 0.0] = 1.0
            self.feature_stds = stds

        if self.feature_means is None or self.feature_stds is None:
            return x

        return (x - self.feature_means) / self.feature_stds  # type: ignore[no-any-return]

    def fit(self, features: pd.DataFrame, epochs: int = 100, batch_size: int = 32) -> None:
        """
        Train the anomaly detection model on normal traffic patterns.

        Args:
            features: Normal traffic features.
            epochs: Training epochs (applicable to Autoencoder).
            batch_size: Batch size (applicable to Autoencoder).
        """
        if features.empty:
            raise ModelError("Cannot train on empty features DataFrame.")

        # Ensure all columns are numeric
        numeric_features = features.select_dtypes(include=[np.number])
        x_data = numeric_features.values

        if self.model_type == "isolation_forest":
            self.model.fit(x_data)
            self.is_trained = True

        elif self.model_type == "autoencoder":
            input_dim = x_data.shape[1]
            self.model = AutoencoderNet(input_dim)

            # Normalize training features
            x_norm = self._normalize(x_data, train=True)

            x_tensor = torch.tensor(x_norm, dtype=torch.float32)
            dataset = TensorDataset(x_tensor)
            dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

            optimizer = optim.Adam(self.model.parameters(), lr=0.005)
            criterion = nn.MSELoss()

            # Train Autoencoder
            self.model.train()
            for _ in range(epochs):
                for (batch_x,) in dataloader:
                    optimizer.zero_grad()
                    reconstructed = self.model(batch_x)
                    loss = criterion(reconstructed, batch_x)
                    loss.backward()
                    optimizer.step()

            # Compute reconstruction errors on training set to set threshold
            self.model.eval()
            with torch.no_grad():
                reconstructed = self.model(x_tensor)
                # Compute MSE per sample
                errors = torch.mean((reconstructed - x_tensor) ** 2, dim=1).numpy()

            # Set threshold at the percentile corresponding to contamination
            # e.g., if contamination is 5%, threshold is at 95th percentile
            pct = (1.0 - self.contamination) * 100.0
            self.reconstruction_threshold = float(np.percentile(errors, pct))
            self.is_trained = True

        elif self.model_type == "custom":
            if hasattr(self.model, "fit"):
                x_norm = self._normalize(x_data, train=True)
                self.model.fit(x_norm)
                self.is_trained = True
            elif hasattr(self.model, "train"):
                self.model.train(features)
                self.is_trained = True
            else:
                raise ModelError("Custom model must implement 'fit()' or 'train()' method.")

    def detect(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Detect anomalies in traffic features.

        Args:
            features: Features DataFrame to check.

        Returns:
            DataFrame containing anomaly details:
            - anomaly_score: float (0.0 to 1.0, higher means more anomalous).
            - is_anomaly: bool (True if flagged).
            - anomaly_type: str ("DDoS" | "link_failure" | "black_hole" | "normal").
        """
        if not self.is_trained:
            raise ModelError("Model must be trained before calling detect().")

        if features.empty:
            return pd.DataFrame(columns=["anomaly_score", "is_anomaly", "anomaly_type"])

        numeric_features = features.select_dtypes(include=[np.number])
        x_data = numeric_features.values

        if self.model_type == "isolation_forest":
            # decision_function outputs values in [-0.5, 0.5] (lower means more anomalous)
            raw_scores = self.model.decision_function(x_data)
            # Map score to [0.0, 1.0] where 1.0 is extremely anomalous
            # Standard mapping: anomaly_score = clamp(0.5 - raw_score)
            anomaly_scores = np.clip(0.5 - raw_scores, 0.0, 1.0)

            # predict() returns 1 (normal) and -1 (anomaly)
            preds = self.model.predict(x_data)
            is_anomaly = preds == -1

        elif self.model_type == "autoencoder":
            self.model.eval()
            x_norm = self._normalize(x_data, train=False)
            x_tensor = torch.tensor(x_norm, dtype=torch.float32)

            with torch.no_grad():
                reconstructed = self.model(x_tensor)
                # Compute reconstruction error per sample
                mse_errors = torch.mean((reconstructed - x_tensor) ** 2, dim=1).numpy()

            # Map error to score: scale relative to threshold
            # E.g., if error is threshold, score is 0.5. Clamp to [0, 1]
            anomaly_scores = np.clip(
                (mse_errors / (self.reconstruction_threshold + 1e-6)) * 0.5, 0.0, 1.0
            )
            is_anomaly = mse_errors > self.reconstruction_threshold

        elif self.model_type == "custom":
            x_norm = self._normalize(x_data, train=False)
            if hasattr(self.model, "detect"):
                # If custom model implements full detect interface
                return self.model.detect(features)

            # Fallback score logic
            if hasattr(self.model, "decision_function"):
                raw_scores = self.model.decision_function(x_norm)
                anomaly_scores = np.clip(0.5 - raw_scores, 0.0, 1.0)
            elif hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(x_norm)
                if len(probs.shape) > 1 and probs.shape[1] > 1:
                    probs = probs[:, 1]
                anomaly_scores = probs
            else:
                anomaly_scores = np.zeros(len(features))

            if hasattr(self.model, "predict"):
                preds = self.model.predict(x_norm)
                is_anomaly = (preds == -1) | ((preds == 1) & (anomaly_scores >= 0.5))
            else:
                is_anomaly = anomaly_scores >= 0.5

        # Classify anomaly types using heuristics
        anomaly_types = []
        for idx in range(len(features)):
            if not is_anomaly[idx]:
                anomaly_types.append("normal")
                continue

            row = features.iloc[idx]

            # 1. DDoS Heuristic: high byte/packet rate and low entropy (concentrated sources)
            bytes_sec = row.get("bytes_per_second", 0.0)
            src_entropy = row.get("src_ip_entropy", 3.0)

            # 2. Black Hole Heuristic: flow count drops to 0 or very low, or bytes dropped entirely
            flow_count = row.get("flow_count", 1)

            if bytes_sec > 10000000.0 and src_entropy < 1.5:
                anomaly_types.append("DDoS")
            elif flow_count == 0 or bytes_sec < 10.0:
                anomaly_types.append("black_hole")
            else:
                # Default fallback type is link_failure / high utilization congestion
                anomaly_types.append("link_failure")

        return pd.DataFrame(
            {
                "anomaly_score": anomaly_scores,
                "is_anomaly": is_anomaly,
                "anomaly_type": anomaly_types,
            },
            index=features.index,
        )

    def save(self, path: str) -> None:
        """Save model configuration and weights."""
        if not self.is_trained:
            raise ModelError("Cannot save an untrained model.")

        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)

        save_dict = {
            "model_type": self.model_type,
            "is_trained": self.is_trained,
            "contamination": self.contamination,
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
        }

        if self.model_type == "isolation_forest":
            save_dict["model"] = self.model
            joblib.dump(save_dict, path)
        elif self.model_type == "autoencoder":
            save_dict["reconstruction_threshold"] = self.reconstruction_threshold
            save_dict["state_dict"] = self.model.state_dict()
            save_dict["input_dim"] = (
                self.feature_means.shape[0] if self.feature_means is not None else 8
            )
            torch.save(save_dict, path)
        elif self.model_type == "custom":
            if hasattr(self.model, "save"):
                self.model.save(path)
            else:
                save_dict["model"] = self.model
                joblib.dump(save_dict, path)

    def load(self, path: str, allow_unsafe: bool = False) -> None:
        """
        Load model configuration and weights.

        Args:
            path: Path to the model file.
            allow_unsafe: If True, allows insecure deserialization (pickle/joblib).
                         Defaults to False.

        Raises:
            ModelError: If loading fails or insecure file is detected with allow_unsafe=False.
        """
        if not os.path.exists(path):
            raise ModelError(f"Model file not found: {path}")

        try:
            if path.endswith(".pt") or path.endswith(".pth"):
                try:
                    load_dict = torch.load(
                        path,
                        map_location=torch.device("cpu"),
                        weights_only=not allow_unsafe,
                    )
                except Exception as e:
                    if not allow_unsafe:
                        raise ModelError(
                            "Failed to load PyTorch model securely. Set allow_unsafe=True "
                            f"if you trust the source. Error: {e}"
                        ) from e
                    raise
            else:
                if not allow_unsafe:
                    raise ModelError(
                        "Insecure model file detected (joblib/pickle). Loading is blocked for "
                        "security. Set allow_unsafe=True if you trust the source."
                    )
                load_dict = joblib.load(path)
        except ModelError:
            raise
        except Exception as e:
            raise ModelError(f"Failed to load model from {path}: {e}") from e

        self.model_type = load_dict["model_type"]
        self.is_trained = load_dict["is_trained"]
        self.contamination = load_dict.get("contamination", 0.05)
        self.feature_means = load_dict.get("feature_means")
        self.feature_stds = load_dict.get("feature_stds")

        if self.model_type == "isolation_forest":
            self.model = load_dict["model"]
        elif self.model_type == "autoencoder":
            input_dim = load_dict["input_dim"]
            self.model = AutoencoderNet(input_dim)
            self.model.load_state_dict(load_dict["state_dict"])
            self.reconstruction_threshold = load_dict["reconstruction_threshold"]
            self.model.eval()
        elif self.model_type == "custom":
            if "model" in load_dict:
                self.model = load_dict["model"]
            else:
                pass
