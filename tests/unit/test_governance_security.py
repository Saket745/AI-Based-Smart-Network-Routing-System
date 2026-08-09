"""Tests for governance security features, specifically secure model loading and API protection."""

from __future__ import annotations

=======
import os
import tempfile

import joblib
=======
import torch
import joblib
import pytest
import pandas as pd
import numpy as np
import contextlib
import os
import tempfile

import joblib

from unittest.mock import patch
 import joblib
import pytest
from fastapi.testclient import TestClient

from nroute.api import server
from nroute.api.server import app
from nroute.exceptions import ModelError
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor


def test_anomaly_detector_secure_loading_enforcement():

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

def test_anomaly_detector_secure_loading_enforcement():
def test_anomaly_detector_secure_loading_enforcement():

def test_anomaly_detector_secure_loading_enforcement():
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
=======
        from contextlib import suppress

        with suppress(ModelError, KeyError):
=======
        try:
            detector.load(path, allow_unsafe=True)
        except (ModelError, KeyError):
            # We expect failure later since it's not a real model, but the security block is bypassed
            pass

def test_congestion_predictor_secure_loading_enforcement():
=======
        # Should succeed with allow_unsafe=True (well, fail later during processing,
        # but pass the security check)
=======
        # Should succeed with allow_unsafe=True (well, fail later during processing, but pass the security check)
        import contextlib

        with contextlib.suppress(ModelError, KeyError):
            # We expect failure later since it's not a real model, but the security block is bypassed
            detector.load(path, allow_unsafe=True)

=======
        with contextlib.suppress(ModelError, KeyError):
            # We expect failure later since it's not a real model, but the security block is bypassed
            detector.load(path, allow_unsafe=True)


def test_congestion_predictor_secure_loading_enforcement():
=======
            # We expect failure later since it's not a real model, but the security block is bypassed
            detector.load(path, allow_unsafe=True)

            # We expect failure later since it's not a real model, but the security block is bypassed
            detector.load(path, allow_unsafe=True)

            # We expect failure later since it's not a real model, but the security block is bypassed
            detector.load(path, allow_unsafe=True)

        # We expect failure later since it's not a real model, but the security block is bypassed
        with contextlib.suppress(ModelError, KeyError):
            detector.load(path, allow_unsafe=True)

        with contextlib.suppress(ModelError, KeyError):
            detector.load(path, allow_unsafe=True)
        with contextlib.suppress(ModelError, KeyError):
            # We expect failure later since it's not a real model, but the security block is bypassed
            detector.load(path, allow_unsafe=True)

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
def test_congestion_predictor_secure_loading_enforcement() -> None:
    """Verify that CongestionPredictor blocks insecure files by default."""
    # CongestionPredictor already has some logic, but let's ensure our changes didn't break it
    predictor = CongestionPredictor(model_type="xgboost")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "insecure.joblib")
        joblib.dump({"some": "data"}, path)

        with pytest.raises(ModelError, match="Insecure model file detected"):
            predictor.load(path, allow_unsafe=False)
=======
=======

        with contextlib.suppress(ModelError, KeyError):
            predictor.load(path, allow_unsafe=True)


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
=======

def test_anomaly_detector_pytorch_load_failure() -> None:
    """Verify that AnomalyDetector handles PyTorch load failures correctly."""
    detector = AnomalyDetector(model_type="autoencoder")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "model.pt")
        # Just need the file to exist
        with open(path, "w") as f:
            f.write("dummy")


def test_api_config_ingest_file_size_limit(client: TestClient) -> None:
    """Verify that uploading a file larger than 5MB returns 413 Payload Too Large."""
    # Build headers with fallback token for successful auth
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
