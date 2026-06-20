"""Unit tests for the traffic anomaly detector."""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from nroute.exceptions import ModelError
from nroute.ml.anomaly import AnomalyDetector


@pytest.fixture
def normal_traffic_data() -> pd.DataFrame:
    """Generate typical normal flow traffic records."""
    np.random.seed(42)
    data = {
        "bytes_per_second": np.random.normal(5000.0, 500.0, 50),
        "packets_per_second": np.random.normal(10.0, 1.0, 50),
        "flow_count": np.random.randint(10, 30, 50),
        "avg_packet_size": np.random.normal(500.0, 50.0, 50),
        "src_ip_entropy": np.random.normal(3.0, 0.2, 50),
        "dst_ip_entropy": np.random.normal(3.0, 0.2, 50),
        "protocol_entropy": np.random.normal(1.2, 0.1, 50),
        "bytes_std": np.random.normal(2000.0, 200.0, 50),
    }
    return pd.DataFrame(data)


@pytest.fixture
def anomalous_traffic_data() -> pd.DataFrame:
    """Generate distinct types of anomalous flow traffic records."""
    data = [
        # DDoS: High bytes, low source IP entropy (flood from specific src)
        {
            "bytes_per_second": 50000000.0,
            "packets_per_second": 100000.0,
            "flow_count": 5000,
            "avg_packet_size": 500.0,
            "src_ip_entropy": 0.5,
            "dst_ip_entropy": 3.2,
            "protocol_entropy": 0.1,
            "bytes_std": 10000.0,
        },
        # Black hole: Zero traffic flow bytes
        {
            "bytes_per_second": 0.0,
            "packets_per_second": 0.0,
            "flow_count": 0,
            "avg_packet_size": 0.0,
            "src_ip_entropy": 0.0,
            "dst_ip_entropy": 0.0,
            "protocol_entropy": 0.0,
            "bytes_std": 0.0,
        },
    ]
    return pd.DataFrame(data)


def test_anomaly_detector_isolation_forest(
    normal_traffic_data: pd.DataFrame, anomalous_traffic_data: pd.DataFrame
) -> None:
    """Test Isolation Forest anomaly detection, predictions, and save/load."""
    detector = AnomalyDetector(model_type="isolation_forest", contamination=0.1)

    with pytest.raises(ModelError):
        detector.detect(normal_traffic_data)

    detector.fit(normal_traffic_data)
    assert detector.is_trained

    # Detect normal data: mostly false
    normal_results = detector.detect(normal_traffic_data)
    assert len(normal_results) == 50
    assert normal_results["is_anomaly"].sum() < 10  # few false positives allowed

    # Detect anomalous data: both flagged
    anomaly_results = detector.detect(anomalous_traffic_data)
    assert len(anomaly_results) == 2
    assert anomaly_results["is_anomaly"].all()
    assert list(anomaly_results["anomaly_type"]) == ["DDoS", "black_hole"]

    # Save/load round-trip
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "forest_model.joblib")
        detector.save(model_path)

        new_detector = AnomalyDetector()
        new_detector.load(model_path, allow_unsafe=True)

        assert new_detector.model_type == "isolation_forest"
        assert new_detector.is_trained

        new_results = new_detector.detect(anomalous_traffic_data)
        pd.testing.assert_frame_equal(anomaly_results, new_results)


def test_anomaly_detector_autoencoder(
    normal_traffic_data: pd.DataFrame, anomalous_traffic_data: pd.DataFrame
) -> None:
    """Test Autoencoder anomaly detection, predictions, and save/load."""
    detector = AnomalyDetector(model_type="autoencoder", contamination=0.1)

    detector.fit(normal_traffic_data, epochs=10, batch_size=8)
    assert detector.is_trained
    assert detector.reconstruction_threshold > 0.0

    # Detect normal data
    normal_results = detector.detect(normal_traffic_data)
    assert len(normal_results) == 50

    # Detect anomalies
    anomaly_results = detector.detect(anomalous_traffic_data)
    assert len(anomaly_results) == 2
    assert anomaly_results["is_anomaly"].all()

    # Save/load round-trip
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "ae_model.pt")
        detector.save(model_path)

        new_detector = AnomalyDetector()
        new_detector.load(model_path, allow_unsafe=True)

        assert new_detector.model_type == "autoencoder"
        assert new_detector.is_trained

        new_results = new_detector.detect(anomalous_traffic_data)
        pd.testing.assert_frame_equal(anomaly_results, new_results)
