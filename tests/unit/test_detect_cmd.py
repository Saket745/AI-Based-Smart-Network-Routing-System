"""Unit tests for the nroute detect CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from nroute.cli import cli
from nroute.cli.detect_cmd import detect_cmd
from nroute.exceptions import ModelError


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def traffic_file(tmp_path) -> str:
    """Create a dummy traffic CSV file."""
    p = tmp_path / "traffic.csv"
    p.write_text("col1,col2\n1,2")
    return str(p)


@pytest.fixture
def model_file(tmp_path) -> str:
    """Create a dummy model file."""
    p = tmp_path / "model.joblib"
    p.write_text("dummy")
    return str(p)


class TestDetectAnomaliesCLI:
    """Tests for `nroute detect anomalies` command."""

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector")
    def test_anomalies_success_text(
        self,
        mock_detector_cls: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test successful anomaly detection with text output."""
        mock_df = pd.DataFrame(
            {
                "anomaly_score": [0.1, 0.9],
                "is_anomaly": [False, True],
                "anomaly_type": ["normal", "DDoS"],
            }
        )
        mock_read_csv.return_value = pd.DataFrame({"fake": [1, 2]})

        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.return_value = mock_df

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code == 0
        assert "Anomaly Detection Results" in result.output
        assert "DDoS" in result.output
        assert "🟢" in result.output or "NO" in result.output
        assert "🔴" in result.output or "YES" in result.output
        assert "1 anomalies detected out of 2 samples" in result.output
        assert "Anomaly Type" in result.output
        assert "Breakdown" in result.output

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector")
    def test_anomalies_success_json(
        self,
        mock_detector_cls: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test successful anomaly detection with JSON output."""
        mock_df = pd.DataFrame(
            {
                "anomaly_score": [0.1, 0.9],
                "is_anomaly": [False, True],
                "anomaly_type": ["normal", "DDoS"],
            }
        )
        mock_read_csv.return_value = pd.DataFrame({"fake": [1, 2]})

        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.return_value = mock_df

        result = runner.invoke(
            cli,
            [
                "--output-format",
                "json",
                "detect",
                "anomalies",
                "--traffic",
                traffic_file,
                "--model",
                model_file,
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_samples"] == 2
        assert data["anomalies_detected"] == 1
        assert data["anomaly_type_breakdown"]["DDoS"] == 1
        assert len(data["samples"]) == 2
        assert data["samples"][1]["is_anomaly"] is True

    @patch("pandas.read_csv")
    def test_anomalies_load_traffic_fail(
        self,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test failure when traffic data cannot be loaded."""
        mock_read_csv.side_effect = Exception("Read error")

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Failed to load traffic data" in result.output

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector")
    def test_anomalies_load_model_fail(
        self,
        mock_detector_cls: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test failure when model cannot be loaded."""
        mock_read_csv.return_value = pd.DataFrame({"fake": [1]})
        mock_detector = mock_detector_cls.return_value
        mock_detector.load.side_effect = ModelError("Load error")

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Failed to load model" in result.output

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector")
    def test_anomalies_detection_fail(
        self,
        mock_detector_cls: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test failure during detection process."""
        mock_read_csv.return_value = pd.DataFrame({"fake": [1]})
        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.side_effect = ModelError("Detection error")

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Detection failed" in result.output

    @patch("pandas.read_csv")
    def test_anomalies_load_traffic_fail_json(
        self,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test failure when traffic data cannot be loaded (JSON mode)."""
        mock_read_csv.side_effect = Exception("Read error")

        result = runner.invoke(
            cli,
            [
                "--output-format",
                "json",
                "detect",
                "anomalies",
                "--traffic",
                traffic_file,
                "--model",
                model_file,
            ],
        )

        assert result.exit_code != 0
        data = json.loads(result.output)
        assert "error" in data
        assert "Failed to load traffic data" in data["error"]

    @patch("nroute.ml.anomaly.AnomalyDetector")
    def test_anomalies_raw_traffic_csv_transformed(
        self,
        mock_detector_cls: MagicMock,
        runner: CliRunner,
        tmp_path,
    ) -> None:
        """Test that raw traffic CSV with flow records is automatically transformed into feature matrix."""
        raw_traffic = tmp_path / "raw_traffic.csv"
        raw_traffic.write_text(
            "source,destination,bytes,packets,duration,protocol,timestamp\n"
            "node_1,node_2,50000000,10000,1.0,TCP,100.0\n"
            "node_2,node_3,100,2,0.1,UDP,100.5\n"
        )
        model_file = tmp_path / "model.joblib"
        model_file.write_text("dummy")
        model_path = str(model_file)

        mock_df = pd.DataFrame(
            {
                "anomaly_score": [0.85],
                "is_anomaly": [True],
                "anomaly_type": ["DDoS"],
            }
        )
        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.return_value = mock_df

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", str(raw_traffic), "--model", model_path],
        )

        assert result.exit_code == 0
        assert "Anomaly Detection Results" in result.output
        assert "DDoS" in result.output
        mock_detector.detect.assert_called_once()
        # Verify passed features contain the 8 statistical feature columns
        passed_features = mock_detector.detect.call_args[0][0]
        assert "bytes_per_second" in passed_features.columns
        assert "src_ip_entropy" in passed_features.columns

    @patch("nroute.ml.anomaly.AnomalyDetector")
    def test_anomalies_prepared_features_csv_direct(
        self,
        mock_detector_cls: MagicMock,
        runner: CliRunner,
        tmp_path,
    ) -> None:
        """Test that pre-computed feature CSV is passed directly to the detector."""
        feature_file = tmp_path / "features.csv"
        feature_file.write_text(
            "bytes_per_second,packets_per_second,flow_count,avg_packet_size,src_ip_entropy,dst_ip_entropy,protocol_entropy,bytes_std\n"
            "5000.0,100.0,10,50.0,1.5,1.5,0.8,200.0\n"
        )
        model_file = tmp_path / "model2.joblib"
        model_file.write_text("dummy")
        model_path = str(model_file)

        mock_df = pd.DataFrame(
            {
                "anomaly_score": [0.1],
                "is_anomaly": [False],
                "anomaly_type": ["normal"],
            }
        )
        mock_detector = mock_detector_cls.return_value
        mock_detector.detect.return_value = mock_df

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", str(feature_file), "--model", model_path],
        )

        assert result.exit_code == 0
        assert "0 anomalies detected" in result.output
        mock_detector.detect.assert_called_once()
        passed_features = mock_detector.detect.call_args[0][0]
        assert list(passed_features.columns) == [
            "bytes_per_second",
            "packets_per_second",
            "flow_count",
            "avg_packet_size",
            "src_ip_entropy",
            "dst_ip_entropy",
            "protocol_entropy",
            "bytes_std",
        ]
