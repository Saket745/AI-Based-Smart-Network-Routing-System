"""Unit tests for the GNN dataset generation pipeline."""

from __future__ import annotations

import os
import tempfile

import pandas as pd

from nroute.core.topology import Topology
from nroute.ml.datasets.generator import DatasetGenerator


def test_dataset_generator_flow() -> None:
    """Test generating JSON snapshots and Parquet dataset from simulation."""
    # Create small topology
    topo = Topology()
    topo.add_node("A", capacity=1000.0)
    topo.add_node("B", capacity=1000.0)
    topo.add_node("C", capacity=1000.0)
    topo.add_edge("A", "B", bandwidth=100.0, latency=5.0)
    topo.add_edge("B", "C", bandwidth=100.0, latency=5.0)

    # Initialize DatasetGenerator
    generator = DatasetGenerator(
        topology=topo,
        router_alg="dijkstra",
        traffic_model="uniform",
        duration_ticks=5,
        flows_per_tick=2,
        seed=42,
    )

    snapshots = generator.generate_snapshots()
    assert len(snapshots) == 5
    assert snapshots[0]["tick"] == 0
    assert len(snapshots[0]["nodes"]) == 3
    assert len(snapshots[0]["edges"]) == 2

    # Save to temp files
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "snapshots.json")
        generator.save_json_snapshots(snapshots, json_path)
        assert os.path.exists(json_path)

        parquet_dir = os.path.join(tmpdir, "parquet_dataset")
        generator.compile_to_parquet(snapshots, parquet_dir)

        # Verify parquet outputs
        assert os.path.exists(os.path.join(parquet_dir, "node_features.parquet"))
        assert os.path.exists(os.path.join(parquet_dir, "edge_features.parquet"))
        assert os.path.exists(os.path.join(parquet_dir, "global_metrics.parquet"))

        node_df, edge_df, global_df = DatasetGenerator.load_parquet_dataset(parquet_dir)
        assert isinstance(node_df, pd.DataFrame)
        assert isinstance(edge_df, pd.DataFrame)
        assert isinstance(global_df, pd.DataFrame)

        # Ticks should match
        assert list(node_df["tick"].unique()) == [0, 1, 2, 3, 4]
        assert list(edge_df["tick"].unique()) == [0, 1, 2, 3, 4]
        assert list(global_df["tick"].unique()) == [0, 1, 2, 3, 4]
