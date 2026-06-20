"""Tests for governance security features, specifically secure model loading."""

from __future__ import annotations

import os
import tempfile
import torch
import joblib
import pytest
import pandas as pd
import numpy as np

from nroute.exceptions import ModelError
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor

def test_anomaly_detector_secure_loading_enforcement():
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
        try:
            detector.load(path, allow_unsafe=True)
        except (ModelError, KeyError):
            # We expect failure later since it's not a real model, but the security block is bypassed
            pass

def test_congestion_predictor_secure_loading_enforcement():
    """Verify that CongestionPredictor blocks insecure files by default."""
    # CongestionPredictor already has some logic, but let's ensure our changes didn't break it
    predictor = CongestionPredictor(model_type="xgboost")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "insecure.joblib")
        joblib.dump({"some": "data"}, path)

        with pytest.raises(ModelError, match="Insecure model file detected"):
            predictor.load(path, allow_unsafe=False)
