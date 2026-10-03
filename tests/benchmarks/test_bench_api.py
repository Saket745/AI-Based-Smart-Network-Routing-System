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
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from nroute.api.server import _FALLBACK_TOKEN, app, get_engine


@pytest.mark.benchmark
def test_bench_ingest_config_file_write(benchmark: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Benchmark config file upload & write handling in ingest_config."""
    engine = get_engine()
    monkeypatch.setattr(engine, "ingest_config", MagicMock(return_value=["host1", "host2"]))

    sample_config = b"version: '1.0'\ndevices:\n  - name: router1\n" * 50000  # ~2MB file

    async def run_ingest() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/config/ingest",
                files={"file": ("config.yaml", sample_config, "text/yaml")},
                headers={"Authorization": f"Bearer {_FALLBACK_TOKEN}"},
            )
            assert response.status_code == 200

    def sync_runner() -> None:
        asyncio.run(run_ingest())

    benchmark(sync_runner)
