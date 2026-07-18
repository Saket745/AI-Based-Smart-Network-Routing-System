"""Traffic benchmarks using pytest-benchmark."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from nroute.core.traffic import TrafficMatrix


@pytest.mark.benchmark
@pytest.mark.parametrize("n_flows", [1000, 10000])
def test_bench_from_dataframe(n_flows: int, benchmark: Any) -> None:
    """Benchmark TrafficMatrix.from_dataframe."""
    # Generate mock DataFrame
    df = pd.DataFrame(
        {
            "source": [f"N{i}" for i in range(n_flows)],
            "destination": [f"N{i + 1}" for i in range(n_flows)],
            "bytes": np.random.randint(100, 10000, size=n_flows),
            "packets": np.random.randint(1, 100, size=n_flows),
            "duration": np.random.uniform(0.1, 10.0, size=n_flows),
            "protocol": np.random.choice(["TCP", "UDP", "ICMP"], size=n_flows),
            "timestamp": np.random.uniform(100.0, 200.0, size=n_flows),
        }
    )

    benchmark(TrafficMatrix.from_dataframe, df)
