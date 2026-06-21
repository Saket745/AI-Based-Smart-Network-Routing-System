"""Unit tests for the prediction CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from click.testing import CliRunner

from nroute.cli import cli
from nroute.core.topology import Topology

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def sample_topo(tmp_path: Path) -> Path:
    topo = Topology()
    topo.add_node("A")
    topo.add_node("B")
    topo.add_edge("A", "B", bandwidth=1000.0, latency=5.0, utilization=0.1)
    topo_path = tmp_path / "topo.json"
    topo.save(topo_path)
    return topo_path


def test_predict_congestion_basic(runner: CliRunner, sample_topo: Path, tmp_path: Path) -> None:
    """Test predict congestion command with a mocked model."""
    # Create a dummy model file
    model_path = tmp_path / "model.joblib"
    model_path.touch()

    # We need to mock CongestionPredictor.load and CongestionPredictor.predict
    # since we don't want to actually train/load a real model here.

    with (
        patch("nroute.ml.congestion.CongestionPredictor.load"),
        patch(
            "nroute.ml.congestion.CongestionPredictor.predict",
            return_value=pd.DataFrame({"probability": [0.1]}),
        ),
    ):
        result = runner.invoke(
            cli,
            [
                "predict",
                "congestion",
                "--topology",
                str(sample_topo),
                "--model",
                str(model_path),
                "--allow-unsafe",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Congestion Predictions" in result.output
        assert "A -> B" in result.output
        assert "NORMAL" in result.output


def test_predict_congestion_no_edges(runner: CliRunner, tmp_path: Path) -> None:
    """Test predict congestion with empty topology."""
    topo = Topology()
    topo_path = tmp_path / "empty_topo.json"
    topo.save(topo_path)
    model_path = tmp_path / "model.joblib"
    model_path.touch()

    with patch("nroute.ml.congestion.CongestionPredictor.load"):
        result = runner.invoke(
            cli,
            ["predict", "congestion", "--topology", str(topo_path), "--model", str(model_path)],
        )
    assert result.exit_code == 0
    assert "No edges found in topology" in result.output


def test_predict_congestion_load_fail(runner: CliRunner, sample_topo: Path, tmp_path: Path) -> None:
    """Test predict congestion when model loading fails."""
    topo_path = sample_topo
    model_path = tmp_path / "bad_model.joblib"
    model_path.touch()

    from nroute.exceptions import ModelError

    with patch(
        "nroute.ml.congestion.CongestionPredictor.load", side_effect=ModelError("Load failed")
    ):
        result = runner.invoke(
            cli,
            ["predict", "congestion", "--topology", str(topo_path), "--model", str(model_path)],
        )

    assert result.exit_code != 0
    assert "Failed to load model" in result.output


def test_predict_gnn_basic(runner: CliRunner, sample_topo: Path, tmp_path: Path) -> None:
    """Test predict gnn command with a mocked ModelStore and model."""
    import torch

    # We need to mock ModelStore.load_model and FeatureBuilder.build_features
    # We also need a dummy model state.
    mock_model_dir = tmp_path / "gnn_models"
    mock_model_dir.mkdir()

    # Create a dummy metadata file to satisfy ModelStore logic if it were called,
    # but we'll mock the whole store/loading process.

    with (
        patch("nroute.ml.model_store.ModelStore.load_model"),
        patch("nroute.ml.features.builder.FeatureBuilder.build_features") as mock_build,
    ):
        # Mock build_features output
        mock_bundle = MagicMock()
        mock_bundle.to_tensors.return_value = MagicMock(
            node_features=torch.randn(2, 8),
            edge_index=torch.tensor([[0], [1]]),
            edge_features=torch.randn(1, 6),
        )
        mock_build.return_value = mock_bundle

        # Mock model forward pass
        # Logit 0.9 => sigmoid(0.9) approx 0.711
        with patch(
            "nroute.ml.models.gcn.GCNModel.forward",
            return_value=(torch.tensor([0.9]), torch.tensor([0.05])),
        ):
            result = runner.invoke(
                cli,
                [
                    "predict",
                    "gnn",
                    "--topology",
                    str(sample_topo),
                    "--model-type",
                    "gcn",
                    "--model-dir",
                    str(mock_model_dir),
                ],
            )

            assert result.exit_code == 0
            assert "GNN (GCN) Predictions" in result.output
            assert "A -> B" in result.output
            # 0.711 is >= 0.85 * 0.7 (0.595), so it should be AT RISK
            assert "AT RISK" in result.output


def test_predict_gnn_graphsage(runner: CliRunner, sample_topo: Path, tmp_path: Path) -> None:
    """Test predict gnn command with graphsage model type."""
    import torch

    mock_model_dir = tmp_path / "gnn_models_gs"
    mock_model_dir.mkdir()

    with (
        patch("nroute.ml.model_store.ModelStore.load_model"),
        patch("nroute.ml.features.builder.FeatureBuilder.build_features") as mock_build,
    ):
        mock_bundle = MagicMock()
        mock_bundle.to_tensors.return_value = MagicMock(
            node_features=torch.randn(2, 8),
            edge_index=torch.tensor([[0], [1]]),
            edge_features=torch.randn(1, 6),
        )
        mock_build.return_value = mock_bundle

        with patch(
            "nroute.ml.models.graphsage.GraphSAGEModel.forward",
            return_value=(torch.tensor([2.0]), torch.tensor([0.1])),
        ):
            result = runner.invoke(
                cli,
                [
                    "predict",
                    "gnn",
                    "--topology",
                    str(sample_topo),
                    "--model-type",
                    "graphsage",
                    "--model-dir",
                    str(mock_model_dir),
                ],
            )

            assert result.exit_code == 0
            assert "GNN (GRAPHSAGE) Predictions" in result.output
            # sigmoid(2.0) approx 0.88, which is > 0.85 threshold
            assert "CONGESTED" in result.output


def test_predict_gnn_load_fail(runner: CliRunner, sample_topo: Path, tmp_path: Path) -> None:
    """Test predict gnn when model loading fails."""
    mock_model_dir = tmp_path / "gnn_models_fail"
    mock_model_dir.mkdir()

    with patch("nroute.ml.model_store.ModelStore.load_model", side_effect=Exception("Store error")):
        result = runner.invoke(
            cli,
            ["predict", "gnn", "--topology", str(sample_topo), "--model-dir", str(mock_model_dir)],
        )
        assert result.exit_code != 0
        assert "Failed to load model" in result.output
