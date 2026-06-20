"""Congestion predictor model implementing XGBoost and LSTM classifiers."""

from __future__ import annotations

import inspect
import json
import os
import tempfile
import zipfile
from typing import Any, cast

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import xgboost as xgb
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, TensorDataset

from nroute.exceptions import ModelError


class PyTorchLSTM(nn.Module):
    """PyTorch LSTM model for link congestion time-series forecasting."""

    def __init__(self, input_dim: int = 1, hidden_dim: int = 32, num_layers: int = 2) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2 if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch, seq_len, input_dim)
        out, _ = self.lstm(x)
        # Take the output from the last time step
        last_out = out[:, -1, :]
        logits = self.fc(last_out)
        return cast("torch.Tensor", logits)


class CongestionPredictor:
    """
    Predicts link congestion probabilities using XGBoost or LSTM models.
    """

    @property
    def preferred_extension(self) -> str:
        """Get the preferred file extension for saving the model."""
        if self.model_type == "lstm":
            return ".pt"
        return ".joblib"

    def __init__(self, model_type: str = "xgboost", custom_model: Any = None) -> None:
        """
        Initialize the CongestionPredictor.

        Args:
            model_type: "xgboost" | "lstm" | "custom".
            custom_model: Optional custom model instance for "custom" type.
        """
        self.model_type = model_type.lower().strip()
        self.model: Any = None
        self.is_trained = False

        if self.model_type == "xgboost":
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                random_state=42,
                eval_metric="logloss",
            )
        elif self.model_type == "lstm":
            self.model = PyTorchLSTM(input_dim=1, hidden_dim=32, num_layers=2)
        elif self.model_type == "custom":
            if custom_model is None:
                raise ValueError("custom_model must be provided if model_type is 'custom'.")
            self.model = custom_model
            # If the custom model is pre-trained, mark it as trained
            self.is_trained = getattr(custom_model, "is_trained", False)
        else:
            raise ValueError(
                f"Unknown model_type '{model_type}'. Supported: xgboost, lstm, custom."
            )

    def _prepare_lstm_data(self, features: pd.DataFrame) -> torch.Tensor:
        """Extract lag utilization features and shape into (batch, seq_len, 1)."""
        # Look for utilization columns: utilization_t, utilization_t_1, etc.
        util_cols = ["utilization_t"]
        for col in features.columns:
            if col.startswith("utilization_t_"):
                util_cols.append(col)

        # Sort columns to ensure chronological order: oldest to newest
        # e.g., utilization_t_5, utilization_t_4, ..., utilization_t
        def get_lag_idx(name: str) -> int:
            if name == "utilization_t":
                return 0
            return int(name.split("_")[-1])

        sorted_cols = sorted(util_cols, key=get_lag_idx, reverse=True)

        # Extract values
        seq_data = features[sorted_cols].values
        # Shape: (samples, seq_len, 1)
        seq_data = np.expand_dims(seq_data, axis=2).copy()
        return torch.tensor(seq_data, dtype=torch.float32)

    def train(
        self, features: pd.DataFrame, labels: np.ndarray, epochs: int = 100, batch_size: int = 64
    ) -> dict[str, float]:
        """
        Train the congestion prediction model.

        Args:
            features: Features DataFrame.
            labels: Binary labels array matching the features.
            epochs: Number of training epochs (applicable to LSTM).
            batch_size: Batch size (applicable to LSTM).

        Returns:
            A dictionary containing evaluation metrics (accuracy, precision, recall, f1).
        """
        if len(features) != len(labels):
            raise ModelError("Features and labels count must match.")

        if self.model_type == "xgboost":
            # Select numerical columns for training (exclude link identifier metadata)
            train_features = features.select_dtypes(include=[np.number])
            self.model.fit(train_features, labels)
            self.is_trained = True

            # Evaluate on training data
            preds = self.model.predict(train_features)
            probs = self.model.predict_proba(train_features)[:, 1]

        elif self.model_type == "lstm":
            x_tensor = self._prepare_lstm_data(features)
            y_tensor = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)

            dataset = TensorDataset(x_tensor, y_tensor)
            dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

            optimizer = optim.Adam(self.model.parameters(), lr=0.001)
            criterion = nn.BCEWithLogitsLoss()

            self.model.train()
            for _ in range(epochs):
                for batch_x, batch_y in dataloader:
                    optimizer.zero_grad()
                    logits = self.model(batch_x)
                    loss = criterion(logits, batch_y)
                    loss.backward()
                    optimizer.step()

            self.is_trained = True

            # Evaluate
            self.model.eval()
            with torch.no_grad():
                logits = self.model(x_tensor)
                probs = torch.sigmoid(logits).numpy().flatten()
                preds = (probs >= 0.5).astype(int)

        elif self.model_type == "custom":
            if hasattr(self.model, "train"):
                sig = inspect.signature(self.model.train)
                kwargs = {}
                if "epochs" in sig.parameters:
                    kwargs["epochs"] = epochs
                if "batch_size" in sig.parameters:
                    kwargs["batch_size"] = batch_size
                metrics = self.model.train(features, labels, **kwargs)
                self.is_trained = True
                if isinstance(metrics, dict):
                    return metrics
            elif hasattr(self.model, "fit"):
                train_features = features.select_dtypes(include=[np.number])
                self.model.fit(train_features, labels)
                self.is_trained = True
            else:
                raise ModelError("Custom model must implement 'train()' or 'fit()' method.")

            # Evaluate custom model
            preds = self.predict(features)["congested"].values.astype(int)

        # Compute classification metrics
        metrics = {
            "accuracy": float(accuracy_score(labels, preds)),
            "precision": float(precision_score(labels, preds, zero_division=0)),
            "recall": float(recall_score(labels, preds, zero_division=0)),
            "f1": float(f1_score(labels, preds, zero_division=0)),
        }
        return metrics

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Predict congestion probabilities for links.

        Args:
            features: Features DataFrame where each row represents a link.

        Returns:
            DataFrame with index matching input, and columns: congested (bool), probability (float).
        """
        if not self.is_trained:
            raise ModelError("Model must be trained before calling predict().")

        if features.empty:
            return pd.DataFrame(columns=["congested", "probability"])

        # Retain index (link IDs)
        link_ids = features.index

        if self.model_type == "xgboost":
            train_features = features.select_dtypes(include=[np.number])
            probs = self.model.predict_proba(train_features)[:, 1]
            congested = self.model.predict(train_features).astype(bool)

        elif self.model_type == "lstm":
            self.model.eval()
            x_tensor = self._prepare_lstm_data(features)
            with torch.no_grad():
                logits = self.model(x_tensor)
                probs = torch.sigmoid(logits).numpy().flatten()
                congested = probs >= 0.5

        elif self.model_type == "custom":
            train_features = features.select_dtypes(include=[np.number])
            if hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(train_features)
                if len(probs.shape) > 1 and probs.shape[1] > 1:
                    probs = probs[:, 1]
                congested = probs >= 0.5
            elif hasattr(self.model, "predict"):
                preds = self.model.predict(train_features)
                if np.max(preds) <= 1.0 and np.min(preds) >= 0.0 and len(np.unique(preds)) > 2:
                    probs = preds
                    congested = probs >= 0.5
                else:
                    congested = preds.astype(bool)
                    probs = congested.astype(float)
            else:
                raise ModelError("Custom model must implement 'predict()' or 'predict_proba()'.")

        return pd.DataFrame({"congested": congested, "probability": probs}, index=link_ids)

    def save(self, path: str) -> None:
        """
        Save the trained model weights and type information using secure serialization.

        Args:
            path: Path where the model should be saved.
        """
        if not self.is_trained:
            raise ModelError("Cannot save an untrained model.")

        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)

        # Base metadata (JSON-safe primitives only)
        metadata = {
            "model_type": self.model_type,
            "is_trained": self.is_trained,
            "serialization_version": "2.0",
        }

        if self.model_type == "xgboost":
            with tempfile.TemporaryDirectory() as tmpdir:
                # Save metadata
                meta_path = os.path.join(tmpdir, "metadata.json")
                with open(meta_path, "w") as f:
                    json.dump(metadata, f)

                # Save XGBoost model natively as JSON
                model_path = os.path.join(tmpdir, "model.json")
                self.model.save_model(model_path)

                # Zip them together
                with zipfile.ZipFile(path, "w") as zf:
                    zf.write(meta_path, "metadata.json")
                    zf.write(model_path, "model.json")

        elif self.model_type == "lstm":
            # torch.load(..., weights_only=True) allows state_dict and basic types
            save_dict = {
                "metadata": metadata,
                "state_dict": self.model.state_dict(),
            }
            torch.save(save_dict, path)

        elif self.model_type == "custom":
            if hasattr(self.model, "save"):
                self.model.save(path)
            else:
                # For custom models without a save method, we refuse to use joblib
                # by default to avoid insecure serialization.
                raise ModelError(
                    f"Custom model of type {type(self.model)} does not implement a 'save' method. "
                    "Secure serialization for arbitrary custom objects is not supported by default."
                )

    def load(self, path: str, allow_unsafe: bool = False) -> None:
        """
        Load model weights and type information from file.

        Args:
            path: Path to the model file.
            allow_unsafe: If True, allows insecure deserialization (pickle/joblib) for legacy models.
                         Defaults to False.

        Raises:
            ModelError: If loading fails or insecure file is detected with allow_unsafe=False.
        """
        if not os.path.exists(path):
            raise ModelError(f"Model file not found: {path}")

        # Attempt to detect if it's a new format (zip for xgboost/legacy-compatible, or pt)
        try:
            if path.endswith(".pt") or path.endswith(".pth"):
                # Use weights_only=True for PyTorch to prevent arbitrary code execution
                try:
                    load_dict = torch.load(
                        path,
                        map_location=torch.device("cpu"),
                        weights_only=not allow_unsafe,
                    )
                except Exception as e:
                    if not allow_unsafe:
                        raise ModelError(
                            "Failed to load PyTorch model securely. The file might be in a legacy "
                            "format or contain unsafe objects. Set allow_unsafe=True if you trust "
                            f"the source. Error: {e}"
                        ) from e
                    raise
            elif zipfile.is_zipfile(path):
                # New XGBoost format
                with zipfile.ZipFile(path, "r") as zf:
                    with zf.open("metadata.json") as f:
                        metadata = json.load(f)

                    self.model_type = metadata["model_type"]
                    self.is_trained = metadata["is_trained"]

                    if self.model_type == "xgboost":
                        with tempfile.TemporaryDirectory() as tmpdir:
                            zf.extract("model.json", tmpdir)
                            model_path = os.path.join(tmpdir, "model.json")
                            self.model = xgb.XGBClassifier()
                            self.model.load_model(model_path)
                        return
                    else:
                        # Fallback for other zipped models if any
                        raise ModelError(
                            f"Unsupported model type in zip archive: {self.model_type}"
                        )
            else:
                # Legacy or other format
                if not allow_unsafe:
                    raise ModelError(
                        "Insecure model file detected (joblib/pickle). Loading is blocked for "
                        "security. Set allow_unsafe=True if you trust the source."
                    )
                load_dict = joblib.load(path)

            # Process load_dict (for PyTorch or Legacy)
            if "metadata" in load_dict:
                # New PyTorch format
                metadata = load_dict["metadata"]
                self.model_type = metadata["model_type"]
                self.is_trained = metadata["is_trained"]
                if self.model_type == "lstm":
                    self.model = PyTorchLSTM(input_dim=1, hidden_dim=32, num_layers=2)
                    self.model.load_state_dict(load_dict["state_dict"])
                    self.model.eval()
            else:
                # Legacy format
                self.model_type = load_dict["model_type"]
                self.is_trained = load_dict["is_trained"]

                if self.model_type == "xgboost":
                    self.model = load_dict["model"]
                elif self.model_type == "lstm":
                    self.model = PyTorchLSTM(input_dim=1, hidden_dim=32, num_layers=2)
                    self.model.load_state_dict(load_dict["state_dict"])
                    self.model.eval()
                elif self.model_type == "custom":
                    if "model" in load_dict:
                        self.model = load_dict["model"]
                    elif hasattr(self.model, "load"):
                        self.model.load(path)

        except ModelError:
            raise
        except Exception as e:
            raise ModelError(f"Failed to load model from {path}: {e}") from e
