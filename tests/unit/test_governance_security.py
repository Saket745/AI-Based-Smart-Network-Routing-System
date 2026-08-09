"""Tests for governance security features, specifically secure model loading and API protection."""

from __future__ import annotations

import contextlib
import inspect
import os
import tempfile
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nroute.api import server
from nroute.api.server import app
from nroute.exceptions import ModelError
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_models_allow_unsafe_defaults_to_false() -> None:
    """Verify that both model load signatures default allow_unsafe to False."""
    for model_cls in [AnomalyDetector, CongestionPredictor]:
        sig = inspect.signature(model_cls.load)
        assert "allow_unsafe" in sig.parameters
        param = sig.parameters["allow_unsafe"]
        assert param.default is False


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

        # Should succeed with allow_unsafe=True (or rather, bypass security check)
        with contextlib.suppress(ModelError, KeyError):
            detector.load(path, allow_unsafe=True)


def test_congestion_predictor_secure_loading_enforcement() -> None:
    """Verify that CongestionPredictor blocks insecure files by default."""
    predictor = CongestionPredictor(model_type="xgboost")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "insecure.joblib")
        joblib.dump({"some": "data"}, path)

        with pytest.raises(ModelError, match="Insecure model file detected"):
            predictor.load(path, allow_unsafe=False)

        with contextlib.suppress(ModelError, KeyError):
            predictor.load(path, allow_unsafe=True)


def test_anomaly_detector_pytorch_secure_loading_failure() -> None:
    """Verify that AnomalyDetector handles PyTorch secure loading failures."""
    detector = AnomalyDetector(model_type="autoencoder")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "model.pt")
        with open(path, "wb") as f:
            f.write(b"dummy")

        with patch("torch.load", side_effect=RuntimeError("Security breach!")):
            with pytest.raises(ModelError) as excinfo:
                detector.load(path, allow_unsafe=False)
            assert "Failed to load PyTorch model securely" in str(excinfo.value)
            assert "Security breach!" in str(excinfo.value)

            with pytest.raises(ModelError) as excinfo:
                detector.load(path, allow_unsafe=True)
            assert f"Failed to load model from {path}" in str(excinfo.value)
            assert "Security breach!" in str(excinfo.value)


def test_congestion_predictor_pytorch_secure_loading_failure() -> None:
    """Verify that CongestionPredictor handles PyTorch secure loading failures."""
    predictor = CongestionPredictor(model_type="lstm")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "model.pt")
        with open(path, "wb") as f:
            f.write(b"dummy")

        with patch("torch.load", side_effect=RuntimeError("Security breach!")):
            with pytest.raises(ModelError) as excinfo:
                predictor.load(path, allow_unsafe=False)
            assert "Failed to load PyTorch model securely" in str(excinfo.value)
            assert "Security breach!" in str(excinfo.value)

            with pytest.raises(ModelError) as excinfo:
                predictor.load(path, allow_unsafe=True)
            assert f"Failed to load model from {path}" in str(excinfo.value)
            assert "Security breach!" in str(excinfo.value)


def test_api_config_ingest_file_size_limit(client: TestClient) -> None:
    """Verify that uploading a file larger than 5MB returns 413 Payload Too Large."""
    headers = {
        "Authorization": f"Bearer {server._FALLBACK_TOKEN}",
        "Content-Length": str(6 * 1024 * 1024),  # Exceeds 5MB
    }

    # Simulate a file larger than 5MB using a small content with Content-Length header
    # to trigger the early header check.
    response = client.post(
        "/api/config/ingest",
        files={"file": ("config.yaml", b"dummy")},
        headers=headers,
    )
    assert response.status_code == 413
    assert "exceeds maximum limit" in response.json()["detail"]

    # Also test actual content size trigger (when Content-Length is missing but content is > 5MB)
    large_content = b"a" * (5 * 1024 * 1024 + 10)
    response = client.post(
        "/api/config/ingest",
        files={"file": ("config.yaml", large_content)},
        headers={"Authorization": f"Bearer {server._FALLBACK_TOKEN}"},
    )
    assert response.status_code == 413
    assert "exceeds maximum limit" in response.json()["detail"]
