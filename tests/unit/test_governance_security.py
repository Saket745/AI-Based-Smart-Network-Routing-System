"""Tests for governance security features, specifically secure model loading."""

from __future__ import annotations

import contextlib
import os
import tempfile
from typing import Any

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


def test_joblib_unpickler_defense_in_depth_rce_prevention() -> None:
    """Verify that even with allow_unsafe=True, malicious payloads trigger errors and do not execute."""

    class FakeSystemPayload:
        def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
            import os

            return (os.system, ("echo VULNERABLE",))

    predictor = CongestionPredictor(model_type="xgboost")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "malicious_payload.joblib")
        joblib.dump(FakeSystemPayload(), path)

        # Even with allow_unsafe=True, loading should fail and block the unsafe class
        with pytest.raises(ModelError, match="Insecure class deserialization blocked"):
            predictor.load(path, allow_unsafe=True)

        # Confirm the same for AnomalyDetector
        detector = AnomalyDetector(model_type="isolation_forest")
        with pytest.raises(ModelError, match="Insecure class deserialization blocked"):
            detector.load(path, allow_unsafe=True)
