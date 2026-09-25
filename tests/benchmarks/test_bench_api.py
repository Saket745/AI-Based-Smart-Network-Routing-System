"""Benchmarks for API endpoint offloaded operations (path validation and file existence check)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from nroute.api.server import _run_in_executor, _validate_and_check_path

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.benchmark
def test_bench_validate_and_check_path(benchmark: Any, tmp_path: Path) -> None:
    """Benchmark synchronous path validation and existence check function."""
    valid_file = tmp_path / "valid_topology.json"
    valid_file.write_text('{"nodes": [], "edges": []}')

    path_str = str(valid_file)

    def run_check() -> None:
        _validate_and_check_path(path_str)

    benchmark(run_check)


@pytest.mark.benchmark
def test_bench_async_offloaded_file_check(benchmark: Any, tmp_path: Path) -> None:
    """Benchmark async offloaded path validation and existence check via thread executor."""
    valid_file = tmp_path / "valid_topology.json"
    valid_file.write_text('{"nodes": [], "edges": []}')

    path_str = str(valid_file)

    def run_async_check() -> None:
        asyncio.run(_run_in_executor(_validate_and_check_path, path_str))

    benchmark(run_async_check)
