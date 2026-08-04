"""Unit tests for the nroute predict CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    import pathlib

import pandas as pd
import pytest
import torch
from click.testing import CliRunner

from nroute.cli.predict_cmd import predict_cmd


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def topo_file(tmp_path: pathlib.Path) -> str:
    """Create a dummy topology file."""
    p = tmp_path / "topo.json"
    p.write_text("{}")
    return str(p)


@pytest.fixture
def model_file(tmp_path: pathlib.Path) -> str:
    """Create a dummy model file."""
    p = tmp_path / "model.joblib"
    p.write_text("dummy model data")
    return str(p)


@pytest.fixture
def model_dir(tmp_path: pathlib.Path) -> str:
    """Create a dummy model directory."""
    d = tmp_path / "models"
    d.mkdir()
    return str(d)


@pytest.fixture
def mock_topology() -> MagicMock:
    """Create a mock topology with some edges."""
    topo = MagicMock()
    topo.edges = [("A", "B"), ("B", "C")]
    topo.get_edge.side_effect = lambda u, v: {
        "utilization": 0.5,
        "bandwidth": 1000.0,
        "latency": 10.0,
        "jitter": 0.1,
        "packet_loss": 0.0,
    }
    return topo


class TestCongestionPredictCLI:
    """Tests for `nroute predict congestion` command."""

    @patch("nroute.cli.predict_cmd.Topology.load")
    @patch("nroute.ml.congestion.CongestionPredictor")
    def test_congestion_success(
        self,
        mock_predictor_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        model_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test successful congestion prediction."""
        mock_topo_load.return_value = mock_topology
        mock_predictor = MagicMock()
        mock_predictor.predict.return_value = pd.DataFrame({"probability": [0.1, 0.9]})
        mock_predictor_cls.return_value = mock_predictor

        result = runner.invoke(
            predict_cmd,
            ["congestion", "--topology", topo_file, "--model", model_file],
        )

        assert result.exit_code == 0
        assert "Congestion Predictions" in result.output
        assert "A -> B" in result.output
        assert "B -> C" in result.output
        assert "NORMAL" in result.output
        assert "CONGESTED" in result.output
        mock_predictor.load.assert_called_once_with(model_file, allow_unsafe=False)

    @patch("nroute.cli.predict_cmd.Topology.load")
    def test_congestion_topology_load_fail(
        self, mock_topo_load: MagicMock, runner: CliRunner, topo_file: str, model_file: str
    ) -> None:
        """Test failure when topology loading fails."""
        mock_topo_load.side_effect = Exception("Load error")

        result = runner.invoke(
            predict_cmd,
            ["congestion", "--topology", topo_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Failed to load topology" in result.output

    @patch("nroute.cli.predict_cmd.Topology.load")
    @patch("nroute.ml.congestion.CongestionPredictor")
    def test_congestion_model_load_fail(
        self,
        mock_predictor_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        model_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test failure when model loading fails."""
        from nroute.exceptions import ModelError

        mock_topo_load.return_value = mock_topology
        mock_predictor = MagicMock()
        mock_predictor.load.side_effect = ModelError("Load error")
        mock_predictor_cls.return_value = mock_predictor

        result = runner.invoke(
            predict_cmd,
            ["congestion", "--topology", topo_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Failed to load model" in result.output

    @patch("nroute.cli.predict_cmd.Topology.load")
    @patch("nroute.ml.congestion.CongestionPredictor")
    def test_congestion_prediction_fail(
        self,
        mock_predictor_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        model_file: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test failure during prediction."""
        mock_topo_load.return_value = mock_topology
        mock_predictor = MagicMock()
        mock_predictor.predict.side_effect = Exception("Inference error")
        mock_predictor_cls.return_value = mock_predictor

        result = runner.invoke(
            predict_cmd,
            ["congestion", "--topology", topo_file, "--model", model_file],
        )

        assert result.exit_code != 0
        assert "Prediction failed" in result.output

    @patch("nroute.cli.predict_cmd.Topology.load")
    @patch("nroute.ml.congestion.CongestionPredictor")
    def test_congestion_empty_topology(
        self,
        mock_predictor_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        model_file: str,
    ) -> None:
        """Test congestion prediction on empty topology."""
        mock_topo = MagicMock()
        mock_topo.edges = []
        mock_topo_load.return_value = mock_topo
        mock_predictor_cls.return_value = MagicMock()

        result = runner.invoke(
            predict_cmd,
            ["congestion", "--topology", topo_file, "--model", model_file],
        )

        assert result.exit_code == 0
        assert "No edges found in topology" in result.output


class TestGNNPredictCLI:
    """Tests for `nroute predict gnn` command."""

    @patch("nroute.cli.predict_cmd.Topology.load")
    @patch("nroute.ml.model_store.ModelStore")
    @patch("nroute.ml.features.builder.FeatureBuilder")
    @patch("nroute.ml.models.gcn.GCNModel")
    @patch("nroute.ml.models.graphsage.GraphSAGEModel")
    def test_gnn_success_gcn(
        self,
        mock_graphsage_cls: MagicMock,
        mock_gcn_cls: MagicMock,
        mock_builder_cls: MagicMock,
        mock_store_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        model_dir: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test successful GNN prediction with GCN model."""
        mock_topo_load.return_value = mock_topology
        mock_topology.edges = [("A", "B"), ("B", "C")]

        mock_model = MagicMock()
        # Mocking the call: model(node_features, edge_index, edge_features)
        # Returns: (logits, pred_lat)
        mock_model.return_value = (torch.tensor([0.0, 5.0]), torch.tensor([0.1, 0.2]))
        mock_gcn_cls.return_value = mock_model

        mock_bundle = MagicMock()
        mock_bundle.node_features = torch.randn(3, 8)
        mock_bundle.edge_index = torch.tensor([[0, 1], [1, 2]])
        mock_bundle.edge_features = torch.randn(2, 6)
        mock_bundle.to_tensors.return_value = mock_bundle

        mock_builder = MagicMock()
        mock_builder.build_features.return_value = mock_bundle
        mock_builder_cls.return_value = mock_builder

        result = runner.invoke(
            predict_cmd,
            ["gnn", "--topology", topo_file, "--model-type", "gcn", "--model-dir", model_dir],
        )

        assert result.exit_code == 0
        assert "GNN (GCN) Predictions" in result.output
        mock_gcn_cls.assert_called_once()
        mock_graphsage_cls.assert_not_called()

    @patch("nroute.cli.predict_cmd.Topology.load")
    @patch("nroute.ml.model_store.ModelStore")
    @patch("nroute.ml.features.builder.FeatureBuilder")
    @patch("nroute.ml.models.graphsage.GraphSAGEModel")
    def test_gnn_success_graphsage(
        self,
        mock_graphsage_cls: MagicMock,
        mock_builder_cls: MagicMock,
        mock_store_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        model_dir: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test successful GNN prediction with GraphSAGE model."""
        mock_topo_load.return_value = mock_topology
        mock_model = MagicMock()
        mock_model.return_value = (torch.tensor([1.0, -1.0]), torch.tensor([0.05, 0.15]))
        mock_graphsage_cls.return_value = mock_model

        mock_bundle = MagicMock()
        mock_bundle.to_tensors.return_value = mock_bundle
        mock_builder = MagicMock()
        mock_builder.build_features.return_value = mock_bundle
        mock_builder_cls.return_value = mock_builder

        result = runner.invoke(
            predict_cmd,
            ["gnn", "--topology", topo_file, "--model-type", "graphsage", "--model-dir", model_dir],
        )

        assert result.exit_code == 0
        assert "GNN (GRAPHSAGE) Predictions" in result.output
        mock_graphsage_cls.assert_called_once()

    @patch("nroute.cli.predict_cmd.Topology.load")
    @patch("nroute.ml.model_store.ModelStore")
    def test_gnn_model_load_fail(
        self,
        mock_store_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        model_dir: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test failure when GNN model loading fails."""
        mock_topo_load.return_value = mock_topology
        mock_store = MagicMock()
        mock_store.load_model.side_effect = Exception("Store error")
        mock_store_cls.return_value = mock_store

        result = runner.invoke(
            predict_cmd,
            ["gnn", "--topology", topo_file, "--model-dir", model_dir],
        )

        assert result.exit_code != 0
        assert "Failed to load model" in result.output

    @patch("nroute.cli.predict_cmd.Topology.load")
    @patch("nroute.ml.model_store.ModelStore")
    @patch("nroute.ml.features.builder.FeatureBuilder")
    def test_gnn_feature_fail(
        self,
        mock_builder_cls: MagicMock,
        mock_store_cls: MagicMock,
        mock_topo_load: MagicMock,
        runner: CliRunner,
        topo_file: str,
        model_dir: str,
        mock_topology: MagicMock,
    ) -> None:
        """Test failure during feature engineering for GNN."""
        mock_topo_load.return_value = mock_topology
        mock_builder = MagicMock()
        mock_builder.build_features.side_effect = Exception("Feature error")
        mock_builder_cls.return_value = mock_builder

        result = runner.invoke(
            predict_cmd,
            ["gnn", "--topology", topo_file, "--model-dir", model_dir],
        )

        assert result.exit_code != 0
        assert "Feature engineering failed" in result.output
