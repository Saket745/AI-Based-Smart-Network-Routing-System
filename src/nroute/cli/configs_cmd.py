"""CLI commands for managing nroute configuration."""

from __future__ import annotations

from pathlib import Path

import click


@click.group(name="config", help="Manage nroute configurations.")
def config_cmd() -> None:
    """Configuration Management Command Group."""
    pass


@config_cmd.command(name="init", help="Initialize a default configuration file.")
@click.option(
    "--output",
    "-o",
    "output_path",
    default="./nroute.yaml",
    show_default=True,
    help="Target path to write the configuration file.",
)
def init_config(output_path: str) -> None:
    """Initialize a default nroute.yaml configuration file."""
    # Default template configuration content
    template = """# nroute system configuration
# -----------------------------
# Customize settings for CLI, simulation, and API server.

general:
  log_level: "INFO"       # Logging verbosity: DEBUG | INFO | WARNING | ERROR
  log_format: "text"      # Format of logs: json | text
  seed: null              # Global random seed for reproducibility
  output_dir: "./output"  # Default output directory for metrics and results
  cors_origins:           # Allowed origins for the Digital Twin API server
    - "*"

topology:
  default_type: "random"  # Default topology model: random | scale-free | small-world | fat-tree
  default_nodes: 50       # Default node count
  default_edge_probability: 0.1 # Edge probability for random graphs
  default_bandwidth: 1000.0 # Default link bandwidth in Mbps
  default_latency: 5.0    # Default link propagation delay in ms

simulation:
  tick_duration: 1.0      # Duration of each simulation tick in seconds
  max_ticks: 3600         # Maximum duration of simulation runs in ticks
  traffic_model: "gravity" # Traffic generator model: uniform | gravity | hotspot | bursty

ml:
  congestion_model: "xgboost"  # Congestion prediction: xgboost | lstm
  anomaly_model: "isolation_forest" # Anomaly detection: isolation_forest | autoencoder
  rl_algorithm: "ppo"     # Reinforcement learning: ppo | dqn
  prediction_horizon: 10  # Congestion prediction horizon in minutes
  training_epochs: 100    # Training iterations for GNN / RL
  batch_size: 64          # Minibatch size
  learning_rate: 0.001    # Learning rate for neural network parameters

routing:
  default_algorithm: "dijkstra" # Standard routing: dijkstra | bellman-ford | ecmp | rl
  weight_metric: "latency"      # Routing cost metric: latency | utilization | composite
  k_shortest_paths: 3           # Paths count for ECMP / multipath

export:
  format: "json"          # Report file format: json | csv
  include_plots: true     # Automatically generate matplotlib rendering of metrics
  plot_format: "png"      # Plot format: png | svg | pdf
  plot_dpi: 150           # DPI resolution for exported figures

custom_routers: {}        # Registry mapping for custom routing plugins
"""
    dest = Path(output_path)
    if dest.exists():
        click.confirm(f"Configuration file '{dest}' already exists. Overwrite?", abort=True)

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(template, encoding="utf-8")
        click.echo(f"Initialized default configuration file at: {dest}")
    except Exception as e:
        click.echo(f"Error initializing configuration file: {e}", err=True)
        raise SystemExit(1) from e
