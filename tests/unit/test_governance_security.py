"""Tests for governance security features, specifically secure model loading."""

from __future__ import annotations

import contextlib
import os
import tempfile
from unittest.mock import patch

import joblib
import pytest

from nroute.exceptions import ModelError
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor


def test_anomaly_detector_secure_loading_enforcement() -> None:
    """Verify that AnomalyDetector blocks insecure files by default."""
    detector = AnomalyDetector(model_type="isolation_forest")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a "fake" insecure joblib file
        path = os.path.join(tmpdir, "insecure.joblib")
        joblib.dump({"some": "data"}, path)

        # Should fail by default
        with pytest.raises(ModelError, match="Insecure model file detected"):
            detector.load(path, allow_unsafe=False)

        # Should succeed with allow_unsafe=True (well, fail later during processing, but pass the security check)
        with contextlib.suppress(ModelError, KeyError):
            # We expect failure later since it's not a real model, but the security block is bypassed
            detector.load(path, allow_unsafe=True)


def test_congestion_predictor_secure_loading_enforcement() -> None:
    """Verify that CongestionPredictor blocks insecure files by default."""
    # CongestionPredictor already has some logic, but let's ensure our changes didn't break it
    predictor = CongestionPredictor(model_type="xgboost")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "insecure.joblib")
        joblib.dump({"some": "data"}, path)

        with pytest.raises(ModelError, match="Insecure model file detected"):
            predictor.load(path, allow_unsafe=False)


def test_anomaly_detector_pytorch_load_failure() -> None:
    """Verify that AnomalyDetector handles PyTorch load failures correctly."""
    detector = AnomalyDetector(model_type="autoencoder")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "model.pt")
        # Just need the file to exist
        with open(path, "w") as f:
            f.write("dummy")

        with patch("torch.load") as mock_load:
            mock_load.side_effect = RuntimeError("Mocked load failure")

            # Case 1: allow_unsafe=False (default) -> should raise ModelError
            with pytest.raises(ModelError, match="Failed to load PyTorch model securely"):
                detector.load(path, allow_unsafe=False)

            # Case 2: allow_unsafe=True -> should re-raise (wrapped in ModelError by outer block)
            with pytest.raises(ModelError, match="Failed to load model from"):
                detector.load(path, allow_unsafe=True)


def test_congestion_predictor_pytorch_load_failure() -> None:
    """Verify that CongestionPredictor handles PyTorch load failures correctly."""
    predictor = CongestionPredictor(model_type="lstm")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "model.pt")
        # Just need the file to exist
        with open(path, "w") as f:
            f.write("dummy")

        with patch("torch.load") as mock_load:
            mock_load.side_effect = RuntimeError("Mocked load failure")

            # Case 1: allow_unsafe=False (default) -> should raise ModelError
            with pytest.raises(ModelError, match="Failed to load PyTorch model securely"):
                predictor.load(path, allow_unsafe=False)

            # Case 2: allow_unsafe=True -> should re-raise (wrapped in ModelError by outer block)
            with pytest.raises(ModelError, match="Failed to load model from"):
                predictor.load(path, allow_unsafe=True)
