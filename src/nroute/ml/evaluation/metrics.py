"""GNN model evaluation metrics and comparison helpers."""

from __future__ import annotations

import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


class GNNEvaluator:
    """Evaluates GNN predictions against target metrics."""

    @staticmethod
    def evaluate_predictions(
        logits: torch.Tensor,
        labels: torch.Tensor,
        pred_lat: torch.Tensor,
        latencies: torch.Tensor,
    ) -> dict[str, float]:
        """
        Compute multi-task evaluation metrics.

        Args:
            logits: Classification logits of shape [E]
            labels: True binary congestion labels of shape [E]
            pred_lat: Predicted latencies of shape [E]
            latencies: True latencies of shape [E]

        Returns:
            Dictionary of calculated metrics.
        """
        metrics = {}

        # 1. Congestion Classification Metrics
        if logits.size(0) > 0:
            probs = torch.sigmoid(logits).detach().cpu().numpy()
            preds = (probs >= 0.5).astype(int)
            targets = labels.detach().cpu().numpy().astype(int)

            metrics["accuracy"] = float(accuracy_score(targets, preds))
            # Handle zero division warnings when there are no predicted or actual positives
            metrics["precision"] = float(precision_score(targets, preds, zero_division=0))
            metrics["recall"] = float(recall_score(targets, preds, zero_division=0))
            metrics["f1_score"] = float(f1_score(targets, preds, zero_division=0))
        else:
            metrics["accuracy"] = 1.0
            metrics["precision"] = 0.0
            metrics["recall"] = 0.0
            metrics["f1_score"] = 0.0

        # 2. Latency Regression Metrics
        if pred_lat.size(0) > 0:
            y_pred = pred_lat.detach().cpu().numpy()
            y_true = latencies.detach().cpu().numpy()

            mse = float(np.mean((y_pred - y_true) ** 2))
            mae = float(np.mean(np.abs(y_pred - y_true)))

            metrics["mse"] = mse
            metrics["mae"] = mae

            # Pearson Correlation Coefficient
            if len(y_pred) > 1 and np.std(y_pred) > 0.0 and np.std(y_true) > 0.0:
                corr = float(np.corrcoef(y_pred, y_true)[0, 1])
                # Handle possible NaN values in corr coef calculation
                metrics["pearson_corr"] = corr if not np.isnan(corr) else 0.0
            else:
                metrics["pearson_corr"] = 0.0
        else:
            metrics["mse"] = 0.0
            metrics["mae"] = 0.0
            metrics["pearson_corr"] = 0.0

        return metrics
