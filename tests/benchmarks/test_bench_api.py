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
