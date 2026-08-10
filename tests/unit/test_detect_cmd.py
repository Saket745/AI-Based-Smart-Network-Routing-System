"""Unit tests for the nroute detect CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from nroute.cli.detect_cmd import detect_cmd
from nroute.exceptions import ModelError


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def traffic_file(tmp_path) -> str:
    """Create a dummy traffic file to satisfy click.Path(exists=True)."""
    p = tmp_path / "traffic.csv"
    p.write_text("dummy")
    return str(p)


@pytest.fixture
def model_file(tmp_path) -> str:
    """Create a dummy model file to satisfy click.Path(exists=True)."""
    p = tmp_path / "model.joblib"
    p.write_text("dummy")
    return str(p)


class TestDetectAnomaliesCLI:
    """Tests for `nroute detect anomalies` command."""

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector.load")
    @patch("nroute.ml.anomaly.AnomalyDetector.detect")
    def test_anomalies_success(
        self,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test successful anomaly detection."""
        # Setup mock data
        mock_read_csv.return_value = pd.DataFrame({"feat": [1, 2]})
        results = pd.DataFrame(
            {
                "anomaly_score": [0.1, 0.8],
                "is_anomaly": [False, True],
                "anomaly_type": ["normal", "DDoS"],
            }
        )
        mock_detect.return_value = results

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code == 0
        assert "Anomaly Detection Results" in result.output
        assert "1 anomalies detected out of 2 samples" in result.output
        assert "DDoS" in result.output
        assert "Anomaly Type" in result.output
        assert "Breakdown" in result.output
        mock_load.assert_called_once_with(model_file, allow_unsafe=False)

    @patch("pandas.read_csv")
    def test_anomalies_traffic_load_fail(
        self,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test failure when traffic data cannot be loaded."""
        mock_read_csv.side_effect = Exception("CSV read error")

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Failed to load traffic data" in result.output

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector.load")
    def test_anomalies_model_load_fail(
        self,
        mock_load: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test failure when model cannot be loaded."""
        mock_read_csv.return_value = pd.DataFrame({"feat": [1]})
        mock_load.side_effect = ModelError("Invalid model")

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Failed to load model" in result.output

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector.load")
    @patch("nroute.ml.anomaly.AnomalyDetector.detect")
    def test_anomalies_detection_fail(
        self,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test failure during detection process."""
        mock_read_csv.return_value = pd.DataFrame({"feat": [1]})
        mock_detect.side_effect = ModelError("Detection error")

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Detection failed" in result.output

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector.load")
    @patch("nroute.ml.anomaly.AnomalyDetector.detect")
    def test_anomalies_allow_unsafe(
        self,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test the --allow-unsafe flag."""
        mock_read_csv.return_value = pd.DataFrame({"feat": [1]})
        mock_detect.return_value = pd.DataFrame(
            {
                "anomaly_score": [0.1],
                "is_anomaly": [False],
                "anomaly_type": ["normal"],
            }
        )

        result = runner.invoke(
            detect_cmd,
            [
                "anomalies",
                "--traffic",
                traffic_file,
                "--model",
                model_file,
                "--allow-unsafe",
            ],
        )

        assert result.exit_code == 0
        mock_load.assert_called_once_with(model_file, allow_unsafe=True)

    @patch("pandas.read_csv")
    @patch("nroute.ml.anomaly.AnomalyDetector.load")
    @patch("nroute.ml.anomaly.AnomalyDetector.detect")
    def test_anomalies_no_anomalies_found(
        self,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        mock_read_csv: MagicMock,
        runner: CliRunner,
        traffic_file: str,
        model_file: str,
    ) -> None:
        """Test output when no anomalies are detected."""
        mock_read_csv.return_value = pd.DataFrame({"feat": [1]})
        results = pd.DataFrame(
            {
                "anomaly_score": [0.1],
                "is_anomaly": [False],
                "anomaly_type": ["normal"],
            }
        )
        mock_detect.return_value = results

        result = runner.invoke(
            detect_cmd,
            ["anomalies", "--traffic", traffic_file, "--model", model_file],
        )

        assert result.exit_code == 0
        assert "0 anomalies detected" in result.output
        assert "Anomaly Type" not in result.output
