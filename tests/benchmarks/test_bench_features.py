"""Feature extraction performance benchmarks using pytest-benchmark."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.topology import Topology
from nroute.ml.features.extractor import DefaultGraphFeatureExtractor


@pytest.mark.benchmark
@pytest.mark.parametrize("num_nodes", [100, 1000])
def test_bench_default_graph_feature_extraction(num_nodes: int, benchmark: Any) -> None:
    """Benchmark graph feature extraction for representative topology sizes."""
    topology = Topology()
    for index in range(num_nodes):
        topology.add_node(f"node_{index}")

    for index in range(num_nodes):
        topology.add_edge(f"node_{index}", f"node_{(index + 1) % num_nodes}")
        topology.add_edge(f"node_{index}", f"node_{(index + 17) % num_nodes}")

    extractor = DefaultGraphFeatureExtractor()
    benchmark(extractor.extract_features, topology)
