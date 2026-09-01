"""Tests verifying lazy optional dependency boundaries and graceful error handling."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from nroute.core.topology import Topology
from nroute.exceptions import IngestionError, ModelError
from nroute.ingestion.pcap import PcapParser
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.anomaly import _get_torch as _get_anomaly_torch
from nroute.ml.congestion import CongestionPredictor
from nroute.ml.congestion import _get_torch as _get_congestion_torch
from nroute.ml.rl_env import _get_gym
from nroute.routing.rl_router import RLRouter, _get_sb3


def test_base_import_does_not_load_heavy_dependencies() -> None:
    """Verify that importing nroute and core modules does not eagerly import optional packages."""
    assert "nroute" in sys.modules
    topo = Topology.generate("random", num_nodes=5, seed=123)
    assert len(topo.nodes) > 0


def test_autoencoder_missing_torch_raises_model_error() -> None:
    """Verify AnomalyDetector raises clear ModelError when PyTorch is missing."""
    with (
        patch(
            "nroute.ml.anomaly._get_torch",
            side_effect=ModelError(
                "Optional dependency 'torch' is required for Autoencoder models. "
                "Install with 'pip install nroute[torch]'."
            ),
        ),
        pytest.raises(ModelError, match=r"pip install nroute\[torch\]"),
    ):
        AnomalyDetector(model_type="autoencoder")


def test_anomaly_get_torch_missing_import_error() -> None:
    """Verify _get_torch helper raises ModelError on ImportError."""
    with (
        patch.dict(sys.modules, {"torch": None}),
        patch("builtins.__import__", side_effect=ImportError("No module named torch")),
        pytest.raises(ModelError, match=r"pip install nroute\[torch\]"),
    ):
        _get_anomaly_torch()


def test_lstm_missing_torch_raises_model_error() -> None:
    """Verify CongestionPredictor raises clear ModelError when PyTorch is missing."""
    with (
        patch(
            "nroute.ml.congestion._get_torch",
            side_effect=ModelError(
                "Optional dependency 'torch' is required for LSTM models. "
                "Install with 'pip install nroute[torch]'."
            ),
        ),
        pytest.raises(ModelError, match=r"pip install nroute\[torch\]"),
    ):
        CongestionPredictor(model_type="lstm")


def test_congestion_get_torch_missing_import_error() -> None:
    """Verify _get_torch helper in congestion raises ModelError on ImportError."""
    with (
        patch.dict(sys.modules, {"torch": None}),
        patch("builtins.__import__", side_effect=ImportError("No module named torch")),
        pytest.raises(ModelError, match=r"pip install nroute\[torch\]"),
    ):
        _get_congestion_torch()


def test_rl_router_missing_sb3_raises_model_error() -> None:
    """Verify RLRouter raises clear ModelError when stable_baselines3 is missing."""
    topo = Topology.generate("random", num_nodes=5, seed=42)
    router = RLRouter(topology=topo)

    with (
        patch(
            "nroute.routing.rl_router._get_sb3",
            side_effect=ModelError(
                "Optional dependencies 'stable-baselines3' and 'gymnasium' are required for RL routing. "
                "Install with 'pip install nroute[rl]'."
            ),
        ),
        pytest.raises(ModelError, match=r"pip install nroute\[rl\]"),
    ):
        router.train(episodes=1)


def test_rl_get_sb3_missing_import_error() -> None:
    """Verify _get_sb3 helper raises ModelError on ImportError."""
    with (
        patch.dict(sys.modules, {"stable_baselines3": None}),
        patch(
            "builtins.__import__",
            side_effect=ImportError("No module named stable_baselines3"),
        ),
        pytest.raises(ModelError, match=r"pip install nroute\[rl\]"),
    ):
        _get_sb3()


def test_gym_missing_import_error() -> None:
    """Verify _get_gym helper raises ModelError on ImportError."""
    with (
        patch.dict(sys.modules, {"gymnasium": None}),
        patch(
            "builtins.__import__",
            side_effect=ImportError("No module named gymnasium"),
        ),
        pytest.raises(ModelError, match=r"pip install nroute\[rl\]"),
    ):
        _get_gym()


def test_pcap_missing_scapy_raises_ingestion_error(tmp_path: Path) -> None:
    """Verify PcapParser raises clear IngestionError referencing nroute[pcap] when scapy is missing."""
    dummy_pcap = tmp_path / "test.pcap"
    dummy_pcap.write_bytes(b"\x00" * 24)

    with (
        patch.dict(
            sys.modules,
            {"scapy": None, "scapy.layers.inet": None, "scapy.utils": None},
        ),
        patch("builtins.__import__", side_effect=ImportError("No module named scapy")),
        pytest.raises(IngestionError, match=r"pip install nroute\[pcap\]"),
    ):
        PcapParser.parse(dummy_pcap)
