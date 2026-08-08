"""Unit tests for nroute.core.config — load_config() and NRouteConfig."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from nroute.core.config import NRouteConfig, load_config
from nroute.exceptions import ConfigError

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------


def test_load_config_defaults_when_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """load_config() returns defaults when no config file is found."""
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert isinstance(cfg, NRouteConfig)
    assert cfg.general.log_level == "INFO"
    assert cfg.topology.default_nodes == 50
    assert cfg.routing.default_algorithm == "dijkstra"


def test_nroute_config_model_fields() -> None:
    cfg = NRouteConfig()
    assert cfg.ml.rl_algorithm == "ppo"
    assert cfg.simulation.max_ticks == 3600
    assert cfg.export.format == "json"


# ---------------------------------------------------------------------------
# YAML file loading
# ---------------------------------------------------------------------------


def test_load_config_from_yaml_file(tmp_path: Path) -> None:
    config_yaml = tmp_path / "nroute.yaml"
    config_yaml.write_text(
        textwrap.dedent("""\
        general:
          log_level: DEBUG
          seed: 42
        topology:
          default_nodes: 10
        """),
        encoding="utf-8",
    )
    cfg = load_config(path=config_yaml)
    assert cfg.general.log_level == "DEBUG"
    assert cfg.general.seed == 42
    assert cfg.topology.default_nodes == 10
    # Unspecified fields retain defaults
    assert cfg.routing.default_algorithm == "dijkstra"


def test_load_config_invalid_yaml_not_dict(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not a valid YAML dictionary"):
        load_config(path=bad_yaml)


def test_load_config_nonexistent_path_falls_back_to_defaults(tmp_path: Path) -> None:
    """load_config() with a path that doesn't exist falls back to defaults, not an error.

    The load_config() implementation only raises ConfigError when the file exists
    but cannot be parsed.  A missing explicit path silently uses default values.
    """
    cfg = load_config(path=tmp_path / "missing.yaml")
    assert isinstance(cfg, NRouteConfig)
    assert cfg.general.log_level == "INFO"


# ---------------------------------------------------------------------------
# Environment variable overrides
# ---------------------------------------------------------------------------


def test_load_config_env_override_string(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NROUTE_GENERAL_LOG_LEVEL", "WARNING")
    cfg = load_config()
    assert cfg.general.log_level == "WARNING"


def test_load_config_env_override_int(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NROUTE_TOPOLOGY_DEFAULT_NODES", "99")
    cfg = load_config()
    assert cfg.topology.default_nodes == 99


def test_load_config_env_override_float(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NROUTE_TOPOLOGY_DEFAULT_BANDWIDTH", "500.0")
    cfg = load_config()
    assert cfg.topology.default_bandwidth == pytest.approx(500.0)


def test_load_config_env_override_bool_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NROUTE_EXPORT_INCLUDE_PLOTS", "false")
    cfg = load_config()
    assert cfg.export.include_plots is False


def test_load_config_searches_configs_subfolder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_config() searches configs/nroute.yaml in the cwd."""
    monkeypatch.chdir(tmp_path)
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    config_yaml = configs_dir / "nroute.yaml"
    config_yaml.write_text(
        textwrap.dedent("""\
        general:
          log_level: WARNING
          cors_origins:
            - "http://localhost:3000"
            - "http://localhost:8000"
        """),
        encoding="utf-8",
    )
    cfg = load_config()
    assert cfg.general.log_level == "WARNING"
    assert cfg.general.cors_origins == ["http://localhost:3000", "http://localhost:8000"]
