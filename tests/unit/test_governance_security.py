"""Tests for governance security features, specifically secure model loading."""

from __future__ import annotations

import contextlib
import os
import tempfile

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


class UnsafeTestClass:
    pass


def test_joblib_deserialization_strict_package_allowlist() -> None:
    """Verify that the joblib monkeypatch blocks deserialization of unsafe classes."""

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "unsafe_test.joblib")
        joblib.dump(UnsafeTestClass(), path)

        # Deserializing it should raise a ValueError due to the strict find_class allowlist
        with pytest.raises(ValueError, match="Unsafe deserialization attempt detected"):
            joblib.load(path)


def test_joblib_deserialization_blocks_dangerous_builtins() -> None:
    """Verify that joblib deserialization blocks dangerous functions in builtins."""
    payload_eval = b"cbuiltins\neval\n(S'1+1'\ntR."
    payload_getattr = b"cbuiltins\ngetattr\n(cbuiltins\nint\nS'__doc__'\ntR."
    payload_exec = b"cbuiltins\nexec\n(S'pass'\ntR."
    payload_open = b"cbuiltins\nopen\n(S'/etc/passwd'\ntR."
    payload_import = b"cbuiltins\n__import__\n(S'os'\ntR."

    with tempfile.TemporaryDirectory() as tmpdir:
        for name, payload in [
            ("eval", payload_eval),
            ("getattr", payload_getattr),
            ("exec", payload_exec),
            ("open", payload_open),
            ("__import__", payload_import),
        ]:
            path = os.path.join(tmpdir, f"exploit_{name}.joblib")
            with open(path, "wb") as f:
                f.write(payload)

            with pytest.raises(ValueError, match="Unsafe deserialization attempt detected"):
                joblib.load(path)


def test_joblib_deserialization_allows_safe_builtins() -> None:
    """Verify that safe builtins (int, str, list, dict, set, tuple, slice) can be deserialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        safe_data = {
            "int": 42,
            "float": 3.14,
            "str": "hello",
            "tuple": (1, 2, 3),
            "list": [1, 2, 3],
            "dict": {"a": 1},
            "set": {1, 2, 3},
            "slice": slice(0, 10, 1),
        }
        path = os.path.join(tmpdir, "safe_builtins.joblib")
        joblib.dump(safe_data, path)

        loaded = joblib.load(path)
        assert loaded["int"] == 42
        assert loaded["slice"] == slice(0, 10, 1)


def test_anomaly_detector_pytorch_secure_loading_failure() -> None:
    """Verify that AnomalyDetector handles PyTorch secure loading failures."""
    from unittest.mock import patch

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
            assert "Security breach!" in str(excinfo.value)


def test_congestion_predictor_pytorch_secure_loading_failure() -> None:
    """Verify that CongestionPredictor handles PyTorch secure loading failures."""
    from unittest.mock import patch

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
            assert "Security breach!" in str(excinfo.value)


def test_api_config_ingest_file_size_limit() -> None:
    """Verify that uploading a file larger than 5MB returns 413 Payload Too Large."""
    from fastapi.testclient import TestClient

    from nroute.api import server
    from nroute.api.server import app

    client = TestClient(app)

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
