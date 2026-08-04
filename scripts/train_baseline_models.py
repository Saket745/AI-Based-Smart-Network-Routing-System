#!/usr/bin/env python3
"""
Script to train and save baseline models for the Network Route Optimizer.
Generates and saves:
1. models/congestion_xgb_v1.joblib (XGBoost)
2. models/anomaly_iforest_v1.joblib (Isolation Forest)
3. models/rl_ppo_v1.zip (PPO agent, default 10k episodes)
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add src directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from nroute.core.topology import Topology
from nroute.ml.anomaly import AnomalyDetector
from nroute.ml.congestion import CongestionPredictor
from nroute.routing.rl_router import RLRouter


def train_congestion_model(topo_path: Path, output_path: Path, seed: int) -> None:
    print("\n--- Training Congestion Prediction Model (XGBoost) ---")
    rng = np.random.default_rng(seed)
    n_samples = 500

    # Generate synthetic training features
    features = pd.DataFrame(
        {
            "utilization": rng.uniform(0, 1, n_samples),
            "bandwidth": rng.uniform(100, 10000, n_samples),
            "latency": rng.uniform(1, 50, n_samples),
            "jitter": rng.uniform(0.1, 5, n_samples),
            "packet_loss": rng.uniform(0, 0.05, n_samples),
            "flow_count": rng.integers(0, 50, n_samples),
            "queue_depth": rng.uniform(0, 100, n_samples),
        }
    )
    # Binary labels: congested if utilization > 0.75
    labels = (features["utilization"] > 0.75).astype(int).values

    print(f"Training XGBoost on {n_samples} samples...")
    predictor = CongestionPredictor(model_type="xgboost")
    metrics = predictor.train(features, labels)
    print(f"Training metrics: {metrics}")

    print(f"Saving model to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    predictor.save(str(output_path))
    print("XGBoost model saved successfully.")

    # Verification
    print("Verifying model reload...")
    reloaded = CongestionPredictor(model_type="xgboost")
    reloaded.load(str(output_path))
    test_pred = reloaded.predict(features.iloc[:5])
    print(f"Sample prediction output:\n{test_pred}")


def train_anomaly_model(topo_path: Path, output_path: Path, seed: int) -> None:
    print("\n--- Training Anomaly Detection Model (Isolation Forest) ---")
    rng = np.random.default_rng(seed)
    n_samples = 500

    # Generate synthetic normal training features
    features = pd.DataFrame(
        {
            "bytes_per_second": rng.uniform(1000, 100000, n_samples),
            "packets_per_second": rng.uniform(10, 1000, n_samples),
            "flow_count": rng.integers(1, 50, n_samples),
            "avg_packet_size": rng.uniform(64, 1500, n_samples),
            "src_ip_entropy": rng.uniform(2.0, 4.0, n_samples),
            "dst_port_entropy": rng.uniform(1.5, 3.5, n_samples),
            "utilization": rng.uniform(0, 0.7, n_samples),
            "latency_avg": rng.uniform(1, 30, n_samples),
        }
    )

    print(f"Training Isolation Forest on {n_samples} samples...")
    detector = AnomalyDetector(model_type="isolation_forest", contamination=0.05)
    detector.fit(features)

    print(f"Saving model to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    detector.save(str(output_path))
    print("Anomaly model saved successfully.")

    # Verification
    print("Verifying model reload...")
    reloaded = AnomalyDetector(model_type="isolation_forest")
    reloaded.load(str(output_path), allow_unsafe=True)
    # Generate one anomalous feature row
    anomalous_features = pd.DataFrame(
        {
            "bytes_per_second": [1000000.0],  # Way too high
            "packets_per_second": [10000.0],
            "flow_count": [200],
            "avg_packet_size": [1500.0],
            "src_ip_entropy": [1.0],
            "dst_port_entropy": [1.0],
            "utilization": [0.99],
            "latency_avg": [250.0],
        }
    )
    score = reloaded.model.score_samples(anomalous_features.values)
    print(f"Anomalous sample score (lower is more anomalous): {score[0]:.4f}")


def train_rl_model(topo_path: Path, output_path: Path, episodes: int, seed: int) -> None:
    print(f"\n--- Training RL Routing Model (PPO for {episodes} episodes) ---")
    topo = Topology.load(str(topo_path))
    print(f"Loaded topology context: {topo.node_count} nodes, {topo.edge_count} edges.")

    router = RLRouter(topology=topo, algorithm="ppo")
    metrics = router.train(episodes=episodes, seed=seed)
    print(f"Training completed. Metrics: {metrics}")

    print(f"Saving model to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    router.save(str(output_path))
    print("RL model and metadata saved successfully.")

    # Verification
    print("Verifying model reload...")
    reloaded = RLRouter(topology=topo, algorithm="ppo")
    reloaded.load(str(output_path))
    # Test path inference from node '0' to node '9'
    path = reloaded.compute_path(topo, "0", "9")
    print(f"Sample path from 0 to 9: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train baseline ML and RL models.")
    parser.add_argument(
        "--topo",
        type=Path,
        default=Path("data/sample_topology.json"),
        help="Path to topology JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models"),
        help="Output directory for saved models.",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=10000,
        help="Number of training episodes for the RL agent (PPO). Default is 10000.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for data generation and model training.",
    )

    args = parser.parse_args()

    # Paths for output files
    congestion_path = args.output_dir / "congestion_xgb_v1.joblib"
    anomaly_path = args.output_dir / "anomaly_iforest_v1.joblib"
    rl_path = args.output_dir / "rl_ppo_v1.zip"

    # Train and save each model
    train_congestion_model(args.topo, congestion_path, args.seed)
    train_anomaly_model(args.topo, anomaly_path, args.seed)
    train_rl_model(args.topo, rl_path, args.episodes, args.seed)

    print("\n=============================================")
    print("All baseline models trained successfully!")
    print(f"Congestion Model:   {congestion_path} ({congestion_path.stat().st_size / 1024:.1f} KB)")
    print(f"Anomaly Model:      {anomaly_path} ({anomaly_path.stat().st_size / 1024:.1f} KB)")
    print(f"RL Model:           {rl_path} ({rl_path.stat().st_size / 1024:.1f} KB)")
    print(
        f"RL Metadata:        {rl_path}.meta ({Path(str(rl_path) + '.meta').stat().st_size / 1024:.1f} KB)"
    )
    print("=============================================")


if __name__ == "__main__":
    main()
