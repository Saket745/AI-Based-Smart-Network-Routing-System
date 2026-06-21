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


@pytest.mark.parametrize(
    ("env_val", "expected"),
    [
        ("true", True),
        ("1", True),
        ("yes", True),
        ("TRUE", True),
        ("Yes", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("maybe", False),
    ],
)
def test_load_config_env_override_bool_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env_val: str, expected: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NROUTE_EXPORT_INCLUDE_PLOTS", env_val)
    cfg = load_config()
    assert cfg.export.include_plots is expected


def test_load_config_env_invalid_int(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Env var casting failure should fall back to raw string and fail Pydantic validation."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NROUTE_TOPOLOGY_DEFAULT_NODES", "not-an-int")
    with pytest.raises(ConfigError, match="Validation of configuration failed"):
        load_config()


# ---------------------------------------------------------------------------
# Advanced Scenarios
# ---------------------------------------------------------------------------


def test_load_config_search_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """yaml should take precedence over yml."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nroute.yml").write_text("general:\n  log_level: WARNING", encoding="utf-8")
    (tmp_path / "nroute.yaml").write_text("general:\n  log_level: DEBUG", encoding="utf-8")

    cfg = load_config()
    assert cfg.general.log_level == "DEBUG"


def test_load_config_home_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test loading config from home directory (~/.nroute/config.yaml)."""
    fake_home = tmp_path / "home"
    config_dir = fake_home / ".nroute"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("general:\n  seed: 123", encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    # Ensure current directory doesn't have a config file
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)

    cfg = load_config()
    assert cfg.general.seed == 123


def test_load_config_validation_error(tmp_path: Path) -> None:
    """Configuration with invalid types should raise ConfigError."""
    config_yaml = tmp_path / "nroute.yaml"
    config_yaml.write_text("topology:\n  default_nodes: not-an-int", encoding="utf-8")
    with pytest.raises(ConfigError, match="Validation of configuration failed"):
        load_config(path=config_yaml)


def test_load_config_permission_error(tmp_path: Path) -> None:
    """Test that file system errors raise ConfigError."""
    config_yaml = tmp_path / "nroute.yaml"
    config_yaml.write_text("general:\n  log_level: DEBUG", encoding="utf-8")
    config_yaml.chmod(0)  # Remove all permissions

    try:
        # On some environments (like running as root), chmod 0 might not block reading.
        # We check if we can read it first; if we can, the test is invalid for this env.
        try:
            with open(config_yaml, encoding="utf-8") as f:
                f.read()
            pytest.skip("Environment allows reading even with chmod 0")
        except PermissionError:
            pass

        with pytest.raises(ConfigError, match="Failed to read configuration"):
            load_config(path=config_yaml)
    finally:
        config_yaml.chmod(0o644)


def test_load_config_with_custom_routers(tmp_path: Path) -> None:
    """Test that custom_routers mapping is correctly loaded."""
    config_yaml = tmp_path / "nroute.yaml"
    config_yaml.write_text(
        textwrap.dedent("""\
        custom_routers:
          my_algo: my_module:MyRouter
        """),
        encoding="utf-8",
    )
    cfg = load_config(path=config_yaml)
    assert cfg.custom_routers == {"my_algo": "my_module:MyRouter"}


def test_load_config_empty_file(tmp_path: Path) -> None:
    """An empty file should result in default configuration."""
    empty_yaml = tmp_path / "nroute.yaml"
    empty_yaml.write_text("", encoding="utf-8")
    cfg = load_config(path=empty_yaml)
    assert isinstance(cfg, NRouteConfig)
    assert cfg.general.log_level == "INFO"


def test_load_config_yml_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback to .yml if .yaml is not present."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nroute.yml").write_text("general:\n  log_level: WARNING", encoding="utf-8")
    cfg = load_config()
    assert cfg.general.log_level == "WARNING"


def test_load_config_env_override_non_existent_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Environment variables for non-existent sections should be ignored."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NROUTE_NOSUCHSECTION_KEY", "value")
    # This should not raise any error
    cfg = load_config()
    assert not hasattr(cfg, "nosuchsection")


def test_load_config_env_override_custom_routers_limitation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Currently, load_config has a limitation where it splits only once on underscore.
    Sections with underscores like 'custom_routers' cannot be easily overridden via env vars.
    This test documents this behavior.
    """
    monkeypatch.chdir(tmp_path)
    # This will be split into section='custom', key='routers_myalgo'
    monkeypatch.setenv("NROUTE_CUSTOM_ROUTERS_MYALGO", "module:Class")
    cfg = load_config()
    # It won't be in custom_routers because 'custom' is not a valid section
    assert "myalgo" not in cfg.custom_routers
    assert cfg.custom_routers == {}
