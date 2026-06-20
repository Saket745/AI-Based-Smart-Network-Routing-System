"""Unit tests for the nroute train CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nroute.cli.train_cmd import train_cmd
from nroute.core.topology import Topology


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_topology(tmp_path: Path) -> str:
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B")
    topo_path = tmp_path / "test_topo.json"
    topo.save(str(topo_path))
    return str(topo_path)


def test_train_group_help(runner: CliRunner) -> None:
    """Test 'train' group help output."""
    result = runner.invoke(train_cmd, ["--help"])
    assert result.exit_code == 0
    assert "Train ML/RL models" in result.output
    assert "congestion" in result.output
    assert "anomaly" in result.output
    assert "rl" in result.output
    assert "gnn" in result.output


def test_train_congestion_success(runner: CliRunner, mock_topology: str, tmp_path: Path) -> None:
    """Test 'train congestion' success path with mocking."""
    output_path = tmp_path / "model.joblib"

    with patch("nroute.ml.congestion.CongestionPredictor") as mock_predictor_cls:
        mock_predictor = MagicMock()
        mock_predictor_cls.return_value = mock_predictor

        # We also need to mock SimulationEngine to avoid long runs
        with patch("nroute.simulation.engine.SimulationEngine.run") as mock_run:
            mock_run.return_value = MagicMock()

            result = runner.invoke(
                train_cmd, ["congestion", "--topology", mock_topology, "--output", str(output_path)]
            )

            assert result.exit_code == 0
            assert "Congestion model saved" in result.output
            mock_predictor.train.assert_called_once()
            mock_predictor.save.assert_called_once_with(str(output_path))


def test_train_anomaly_success(runner: CliRunner, mock_topology: str, tmp_path: Path) -> None:
    """Test 'train anomaly' success path with mocking."""
    output_path = tmp_path / "anomaly.joblib"

    with patch("nroute.ml.anomaly.AnomalyDetector") as mock_detector_cls:
        mock_detector = MagicMock()
        mock_detector_cls.return_value = mock_detector

        result = runner.invoke(
            train_cmd, ["anomaly", "--topology", mock_topology, "--output", str(output_path)]
        )

        assert result.exit_code == 0
        assert "Anomaly model saved" in result.output
        mock_detector.fit.assert_called_once()
        mock_detector.save.assert_called_once_with(str(output_path))


def test_train_rl_success(runner: CliRunner, mock_topology: str, tmp_path: Path) -> None:
    """Test 'train rl' success path with mocking."""
    output_path = tmp_path / "rl_model"

    with patch("nroute.routing.rl_router.RLRouter") as mock_router_cls:
        mock_router = MagicMock()
        mock_router_cls.return_value = mock_router

        result = runner.invoke(
            train_cmd,
            ["rl", "--topology", mock_topology, "--output", str(output_path), "--timesteps", "100"],
        )

        assert result.exit_code == 0
        assert "RL model saved" in result.output
        mock_router.train.assert_called_once()
        mock_router.save.assert_called_once_with(str(output_path))


def test_train_gnn_success(runner: CliRunner, mock_topology: str, tmp_path: Path) -> None:
    """Test 'train gnn' success path with mocking."""
    output_dir = tmp_path / "gnn_model"
    dataset_dir = tmp_path / "gnn_dataset"

    # Mock many things to avoid actual training and heavy dependencies
    with (
        patch("nroute.ml.datasets.generator.DatasetGenerator") as mock_gen_cls,
        patch("nroute.ml.training.trainer.GNNTrainer") as mock_trainer_cls,
        patch("nroute.ml.model_store.ModelStore") as mock_store_cls,
        patch("torch.utils.data.DataLoader"),
        patch("nroute.ml.models.gcn.GCNModel"),
    ):
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate_snapshots.return_value = []

        # Mock static method and make tick selection work
        node_df = MagicMock()
        node_df.__getitem__.return_value.unique.return_value = [1, 2, 3, 4, 5]
        node_df.isin.return_value = [True, True]
        mock_gen_cls.load_parquet_dataset.return_value = (node_df, MagicMock(), MagicMock())

        mock_trainer = mock_trainer_cls.return_value
        mock_trainer.train_epoch.return_value = {"loss": 0.1, "cls_loss": 0.05, "reg_loss": 0.05}
        mock_trainer.evaluate.return_value = {"val_loss": 0.1}

        mock_store = mock_store_cls.return_value
        mock_store.save_model.return_value = str(output_dir / "gcn_v1.pt")

        result = runner.invoke(
            train_cmd,
            [
                "gnn",
                "--topology",
                mock_topology,
                "--output-dir",
                str(output_dir),
                "--dataset-dir",
                str(dataset_dir),
                "--epochs",
                "1",
            ],
        )

        assert result.exit_code == 0
        assert "GNN model saved" in result.output


def test_train_missing_topology(runner: CliRunner) -> None:
    """Test failure when topology file does not exist."""
    result = runner.invoke(train_cmd, ["congestion", "--topology", "nonexistent.json"])
    assert result.exit_code != 0
    assert "Path 'nonexistent.json' does not exist" in result.output


def test_train_invalid_topology_content(runner: CliRunner, tmp_path: Path) -> None:
    """Test failure when topology file is invalid JSON."""
    bad_topo = tmp_path / "bad.json"
    bad_topo.write_text("not json")

    result = runner.invoke(train_cmd, ["congestion", "--topology", str(bad_topo)])
    assert result.exit_code != 0
    assert "Failed to load topology" in result.output


def test_train_congestion_model_error(runner: CliRunner, mock_topology: str) -> None:
    """Test 'train congestion' error handling."""
    from nroute.exceptions import ModelError

    with (
        patch("nroute.ml.congestion.CongestionPredictor") as mock_predictor_cls,
        patch("nroute.simulation.engine.SimulationEngine.run"),
    ):
        mock_predictor = mock_predictor_cls.return_value
        mock_predictor.train.side_effect = ModelError("Mocked training error")

        result = runner.invoke(train_cmd, ["congestion", "--topology", mock_topology])

        assert result.exit_code == 1
        assert "Training error: Mocked training error" in result.output


def test_train_anomaly_model_error(runner: CliRunner, mock_topology: str) -> None:
    """Test 'train anomaly' error handling."""
    from nroute.exceptions import ModelError

    with patch("nroute.ml.anomaly.AnomalyDetector") as mock_detector_cls:
        mock_detector = mock_detector_cls.return_value
        mock_detector.fit.side_effect = ModelError("Mocked anomaly error")

        result = runner.invoke(train_cmd, ["anomaly", "--topology", mock_topology])

        assert result.exit_code == 1
        assert "Training error: Mocked anomaly error" in result.output


def test_train_rl_error(runner: CliRunner, mock_topology: str) -> None:
    """Test 'train rl' error handling."""
    with patch("nroute.routing.rl_router.RLRouter") as mock_router_cls:
        mock_router = mock_router_cls.return_value
        mock_router.train.side_effect = Exception("Mocked RL error")

        result = runner.invoke(train_cmd, ["rl", "--topology", mock_topology])

        assert result.exit_code == 1
        assert "RL training error: Mocked RL error" in result.output
