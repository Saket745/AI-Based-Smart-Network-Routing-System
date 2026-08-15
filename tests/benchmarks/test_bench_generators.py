"""Topology generator benchmarks using pytest-benchmark."""

from __future__ import annotations

from typing import Any

import pytest

from nroute.core.generators import TopologyGenerator


@pytest.mark.benchmark
@pytest.mark.parametrize("k", [8, 16, 32])
def test_bench_fat_tree(k: int, benchmark: Any) -> None:
    """Benchmark fat-tree topology generation across representative sizes."""
    benchmark(TopologyGenerator.fat_tree, k)
