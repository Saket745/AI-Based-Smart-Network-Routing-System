"""Tests for governance security features, specifically secure model loading."""

from __future__ import annotations

import contextlib
import inspect
import os
import tempfile
from unittest.mock import patch

import joblib
import pytest

from nroute.exceptions import ModelError
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor


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

        # Should succeed with allow_unsafe=True (well, fail later during processing, but pass the security check)
        with contextlib.suppress(ModelError, KeyError):
            detector.load(path, allow_unsafe=True)


def test_anomaly_detector_pytorch_secure_loading_failure() -> None:
    """Verify that AnomalyDetector handles PyTorch secure loading failures."""
    detector = AnomalyDetector()
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
    predictor = CongestionPredictor(model_type="xgboost")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "insecure.joblib")
        joblib.dump({"some": "data"}, path)

        with pytest.raises(ModelError, match="Insecure model file detected"):
            predictor.load(path, allow_unsafe=False)


def test_congestion_predictor_pytorch_secure_loading_failure() -> None:
    """Verify that CongestionPredictor handles PyTorch secure loading failures."""
    predictor = CongestionPredictor()
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
            assert "Failed to load PyTorch model securely" in str(excinfo.value)
            assert "Security breach!" in str(excinfo.value)


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

            # Case 2: allow_unsafe=True -> should still raise secure load failure because allow_unsafe is ignored
            with pytest.raises(ModelError, match="Failed to load PyTorch model securely"):
                predictor.load(path, allow_unsafe=True)


def test_api_ingest_config_file_size_limit() -> None:
    """Verify that POST /api/config/ingest enforces the 5MB file size limit to prevent OOM DoS."""
    from fastapi.testclient import TestClient

    from nroute.api.server import _FALLBACK_TOKEN, app

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}

    # Case 1: Large file exceeds 5MB
    large_content = b"x" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/config/ingest",
        files={"file": ("config.yaml", large_content, "application/x-yaml")},
        headers=headers,
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed limit of 5MB" in response.json()["detail"]

    # Case 2: Small file under 5MB (should bypass the size limit check)
    small_content = b"hostname: R1\n"
    # We patch the engine so we do not actually try to load/parse the mock config
    with patch("nroute.api.server._run_in_executor", return_value=["R1"]):
        response = client.post(
            "/api/config/ingest",
            files={"file": ("config.yaml", small_content, "application/x-yaml")},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
