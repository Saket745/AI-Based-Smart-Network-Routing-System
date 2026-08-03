"""Traffic ingestion benchmarks using pytest-benchmark."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from nroute.core.traffic import TrafficMatrix


@pytest.mark.benchmark
@pytest.mark.parametrize("num_flows", [1000, 10000])
def test_bench_traffic_from_dataframe(num_flows: int, benchmark: Any) -> None:
    """Benchmark creating a TrafficMatrix from a pandas DataFrame of varying sizes."""
    df = pd.DataFrame(
        {
            "source": [f"Node_{i % 10}" for i in range(num_flows)],
            "destination": [f"Node_{(i + 1) % 10}" for i in range(num_flows)],
            "bytes": [1000 + i for i in range(num_flows)],
            "packets": [10 + i % 5 for i in range(num_flows)],
            "duration": [1.5 + (i % 3) * 0.5 for i in range(num_flows)],
            "protocol": ["TCP" if i % 2 == 0 else "UDP" for i in range(num_flows)],
            "timestamp": [100.0 + i * 0.1 for i in range(num_flows)],
        }
    )

    def run_from_dataframe() -> None:
        TrafficMatrix.from_dataframe(df)

    benchmark(run_from_dataframe)
