"""Configuration models and loaders for the nroute library."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from nroute.exceptions import ConfigError


class GeneralConfig(BaseModel):
    """General system settings."""

    log_level: str = Field(default="INFO", description="DEBUG | INFO | WARNING | ERROR")
    log_format: str = Field(default="text", description="json | text")
    seed: int | None = Field(default=None, description="Global random seed")
    output_dir: str = Field(default="./output", description="Default output directory")


class TopologyConfig(BaseModel):
    """Default topology parameters."""

    default_type: str = Field(
        default="random", description="random | fat-tree | scale-free | small-world"
    )
    default_nodes: int = Field(default=50, description="Default number of nodes")
    default_edge_probability: float = Field(
        default=0.1, description="Default edge probability for random graphs"
    )
    default_bandwidth: float = Field(default=1000.0, description="Default link bandwidth in Mbps")
    default_latency: float = Field(default=5.0, description="Default link propagation delay in ms")


class SimulationConfig(BaseModel):
    """Simulation settings."""

    tick_duration: float = Field(default=1.0, description="Duration of each tick in seconds")
    max_ticks: int = Field(default=3600, description="Maximum number of ticks per simulation run")
    traffic_model: str = Field(
        default="gravity", description="uniform | gravity | hotspot | bursty"
    )


class MLConfig(BaseModel):
    """Machine Learning parameters."""

    congestion_model: str = Field(default="xgboost", description="xgboost | lstm")
    anomaly_model: str = Field(
        default="isolation_forest", description="isolation_forest | autoencoder"
    )
    rl_algorithm: str = Field(default="ppo", description="ppo | dqn")
    prediction_horizon: int = Field(
        default=10, description="Congestion prediction horizon in minutes"
    )
    training_epochs: int = Field(default=100, description="Number of training epochs")
    batch_size: int = Field(default=64, description="Training batch size")
    learning_rate: float = Field(default=0.001, description="Learning rate for ML models")


class RoutingConfig(BaseModel):
    """Routing settings."""

    default_algorithm: str = Field(
        default="dijkstra", description="dijkstra | bellman-ford | ecmp | rl"
    )
    weight_metric: str = Field(default="latency", description="latency | utilization | composite")
    k_shortest_paths: int = Field(default=3, description="Number of paths for ECMP/rerouting")


class ExportConfig(BaseModel):
    """Export and reporting settings."""

    format: str = Field(default="json", description="json | csv")
    include_plots: bool = Field(default=True, description="Whether to generate and save plots")
    plot_format: str = Field(default="png", description="png | svg | pdf")
    plot_dpi: int = Field(default=150, description="DPI for saved plots")


class NRouteConfig(BaseModel):
    """Root configuration model for nroute."""

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    topology: TopologyConfig = Field(default_factory=TopologyConfig)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    custom_routers: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of custom router algorithm names to module:class import strings",
    )


def load_config(path: str | Path | None = None) -> NRouteConfig:
    """
    Load configuration from YAML files and environment variables.

    Searches:
    1. The provided path (if any).
    2. ./nroute.yaml or ./nroute.yml
    3. ~/.nroute/config.yaml or ~/.nroute/config.yml
    4. Default settings.

    Environment variables with prefix NROUTE_ override loaded values.
    For example: NROUTE_GENERAL_LOG_LEVEL=DEBUG

    Args:
        path: Optional file path to configuration.

    Returns:
        Loaded NRouteConfig object.
    """
    config_dict: dict[str, Any] = {}

    # 1. Search for files
    paths_to_try: list[Path] = []
    if path is not None:
        paths_to_try.append(Path(path))
    else:
        paths_to_try.extend(
            [
                Path("nroute.yaml"),
                Path("nroute.yml"),
                Path(os.path.expanduser("~/.nroute/config.yaml")),
                Path(os.path.expanduser("~/.nroute/config.yml")),
            ]
        )

    found_path = None
    for p in paths_to_try:
        if p.is_file():
            found_path = p
            break

    if found_path is not None:
        try:
            with open(found_path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config_dict = loaded
                elif loaded is not None:
                    raise ConfigError(
                        f"Configuration file {found_path} is not a valid YAML dictionary."
                    )
        except Exception as e:
            if isinstance(e, ConfigError):
                raise
            raise ConfigError(f"Failed to read configuration from {found_path}: {e}") from e

    # 2. Merge Environment Variable Overrides
    # Expected format: NROUTE_SECTION_KEY (e.g., NROUTE_GENERAL_LOG_LEVEL)
    for env_key, env_val in os.environ.items():
        if env_key.startswith("NROUTE_"):
            parts = env_key[7:].lower().split("_", 1)
            if len(parts) == 2:
                section, key = parts
                if section in NRouteConfig.model_fields:
                    if section not in config_dict:
                        config_dict[section] = {}

                    # Cast string value based on Pydantic target type if possible
                    section_model_cls = NRouteConfig.model_fields[section].annotation
                    if (
                        section_model_cls
                        and hasattr(section_model_cls, "model_fields")
                        and key in section_model_cls.model_fields
                    ):
                        field_info = section_model_cls.model_fields[key]
                        # Simple type casting
                        try:
                            if field_info.annotation is bool:
                                config_dict[section][key] = env_val.lower() in ("true", "1", "yes")
                                continue
                            if field_info.annotation is int:
                                config_dict[section][key] = int(env_val)
                                continue
                            if field_info.annotation is float:
                                config_dict[section][key] = float(env_val)
                                continue
                        except ValueError:
                            # Fall back to raw string to let Pydantic handle/error
                            pass

                    config_dict[section][key] = env_val

    # 3. Instantiate and validate with Pydantic
    try:
        return NRouteConfig.model_validate(config_dict)
    except Exception as e:
        raise ConfigError(f"Validation of configuration failed: {e}") from e
