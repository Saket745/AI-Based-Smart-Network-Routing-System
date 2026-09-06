"""Unit tests for train CLI subcommands (`train_gnn`)."""

import json

import pytest
from click.testing import CliRunner

from nroute.cli.train_cmd import train_cmd


@pytest.fixture
def temp_topo_file(tmp_path):
    topo_data = {
        "nodes": [
            {"id": "A", "role": "router"},
            {"id": "B", "role": "router"},
            {"id": "C", "role": "switch"},
        ],
        "edges": [
            {"source": "A", "target": "B", "bandwidth": 1000.0, "latency": 10.0},
            {"source": "B", "target": "C", "bandwidth": 1000.0, "latency": 10.0},
        ],
    }
    path = tmp_path / "test_topo.json"
    path.write_text(json.dumps(topo_data))
    return str(path)


class TestTrainGNNCLI:
    def test_train_gnn_gcn_success(self, temp_topo_file, tmp_path):
        runner = CliRunner()
        output_dir = str(tmp_path / "models" / "gnn")
        dataset_dir = str(tmp_path / "data" / "gnn_dataset")

        result = runner.invoke(
            train_cmd,
            [
                "gnn",
                "--topology",
                temp_topo_file,
                "--model-type",
                "gcn",
                "--epochs",
                "1",
                "--output-dir",
                output_dir,
                "--dataset-dir",
                dataset_dir,
            ],
        )

        assert result.exit_code == 0
        assert "Collecting simulation traces" in result.output
        assert "Training GNN model (GCN)" in result.output
        assert "GNN model saved to" in result.output

    def test_train_gnn_graphsage_success(self, temp_topo_file, tmp_path):
        runner = CliRunner()
        output_dir = str(tmp_path / "models" / "gnn_sage")
        dataset_dir = str(tmp_path / "data" / "gnn_dataset_sage")

        result = runner.invoke(
            train_cmd,
            [
                "gnn",
                "--topology",
                temp_topo_file,
                "--model-type",
                "graphsage",
                "--epochs",
                "1",
                "--output-dir",
                output_dir,
                "--dataset-dir",
                dataset_dir,
            ],
        )

        assert result.exit_code == 0
        assert "Training GNN model (GRAPHSAGE)" in result.output
        assert "GNN model saved to" in result.output

    def test_train_gnn_topology_load_failure(self, tmp_path):
        runner = CliRunner()
        invalid_topo = str(tmp_path / "non_existent.json")
        # create an empty file
        with open(invalid_topo, "w") as f:
            f.write("invalid json content")

        result = runner.invoke(
            train_cmd,
            [
                "gnn",
                "--topology",
                invalid_topo,
            ],
        )

        assert result.exit_code == 1
        assert "Failed to load topology" in result.output

    def test_train_gnn_model_save_failure(self, temp_topo_file, tmp_path, monkeypatch):
        runner = CliRunner()
        output_dir = str(tmp_path / "models" / "gnn")
        dataset_dir = str(tmp_path / "data" / "gnn_dataset")

        # Mock ModelStore.save_model to raise an exception
        def mock_save_model(*args, **kwargs):
            raise Exception("Disk write error")

        from nroute.ml.model_store import ModelStore

        monkeypatch.setattr(ModelStore, "save_model", mock_save_model)

        result = runner.invoke(
            train_cmd,
            [
                "gnn",
                "--topology",
                temp_topo_file,
                "--epochs",
                "1",
                "--output-dir",
                output_dir,
                "--dataset-dir",
                dataset_dir,
            ],
        )

        assert result.exit_code == 1
        assert "Saving error: Disk write error" in result.output
