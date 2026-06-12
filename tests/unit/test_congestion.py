"""Unit tests for the link congestion predictor model."""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from nroute.exceptions import ModelError
from nroute.ml.congestion import CongestionPredictor


@pytest.fixture
def dummy_dataset() -> tuple[pd.DataFrame, np.ndarray]:
    """Generate a dummy features DataFrame and labels array for training."""
    # 20 samples, 6 time-series lags
    np.random.seed(42)
    data = {
        "utilization_t": np.random.uniform(0.0, 1.0, 20),
        "utilization_t_1": np.random.uniform(0.0, 1.0, 20),
        "utilization_t_2": np.random.uniform(0.0, 1.0, 20),
        "utilization_t_3": np.random.uniform(0.0, 1.0, 20),
        "utilization_t_4": np.random.uniform(0.0, 1.0, 20),
        "utilization_t_5": np.random.uniform(0.0, 1.0, 20),
        "bandwidth": np.random.choice([100.0, 1000.0, 10000.0], 20),
        "latency": np.random.uniform(1.0, 50.0, 20),
    }
    df = pd.DataFrame(data)
    df.index = [f"node_{i}->node_{i + 1}" for i in range(20)]

    # Label is 1 if current utilization is high
    labels = (df["utilization_t"] > 0.75).astype(int).values
    return df, labels


def test_congestion_predictor_xgboost(dummy_dataset: tuple[pd.DataFrame, np.ndarray]) -> None:
    """Test XGBoost congestion model train, predict, and save/load."""
    df, labels = dummy_dataset
    predictor = CongestionPredictor(model_type="xgboost")

    # Untrained prediction raises error
    with pytest.raises(ModelError):
        predictor.predict(df)

    # Train model
    metrics = predictor.train(df, labels)
    assert "accuracy" in metrics
    assert "f1" in metrics
    assert predictor.is_trained

    # Predict
    preds = predictor.predict(df)
    assert len(preds) == 20
    assert "congested" in preds.columns
    assert "probability" in preds.columns
    assert preds["congested"].dtype == bool
    assert preds["probability"].min() >= 0.0
    assert preds["probability"].max() <= 1.0

    # Save/load round-trip
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "xgb_model.joblib")
        predictor.save(model_path)

        new_predictor = CongestionPredictor()
        new_predictor.load(model_path)

        assert new_predictor.model_type == "xgboost"
        assert new_predictor.is_trained

        new_preds = new_predictor.predict(df)
        pd.testing.assert_frame_equal(preds, new_preds)


def test_congestion_predictor_lstm(dummy_dataset: tuple[pd.DataFrame, np.ndarray]) -> None:
    """Test PyTorch LSTM congestion model train, predict, and save/load."""
    df, labels = dummy_dataset
    predictor = CongestionPredictor(model_type="lstm")

    # Train model
    metrics = predictor.train(df, labels, epochs=5, batch_size=4)
    assert predictor.is_trained
    assert "accuracy" in metrics

    # Predict
    preds = predictor.predict(df)
    assert len(preds) == 20
    assert preds["probability"].min() >= 0.0
    assert preds["probability"].max() <= 1.0

    # Save/load round-trip
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "lstm_model.pt")
        predictor.save(model_path)

        new_predictor = CongestionPredictor()
        new_predictor.load(model_path)

        assert new_predictor.model_type == "lstm"
        assert new_predictor.is_trained

        new_preds = new_predictor.predict(df)
        pd.testing.assert_frame_equal(preds, new_preds)


def test_congestion_predictor_mismatched_inputs(
    dummy_dataset: tuple[pd.DataFrame, np.ndarray],
) -> None:
    """Test validation errors for training dimension mismatches."""
    df, labels = dummy_dataset
    predictor = CongestionPredictor()

    with pytest.raises(ModelError):
        predictor.train(df, labels[:-1])
