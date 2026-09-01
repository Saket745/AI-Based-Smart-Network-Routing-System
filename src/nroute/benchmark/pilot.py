"""Calibrated 120-run benchmark orchestrator and research validation engine for nroute."""

from __future__ import annotations

import json
import platform
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx
import numpy as np
import pandas as pd

from nroute.benchmark.dynamic_dijkstra import DynamicDijkstraRouter
from nroute.benchmark.instrumentation import InstrumentedRouter, PilotMetricsRecorder
from nroute.core.generators import TopologyGenerator
from nroute.routing.ai import AIRouter
from nroute.routing.dijkstra import DijkstraRouter
from nroute.routing.ecmp import ECMPRouter
from nroute.routing.rl_router import RLRouter
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.failure_injector import FailureInjector
from nroute.simulation.traffic_gen import TrafficGenerator

if TYPE_CHECKING:
    from nroute.core.topology import Topology


def get_git_commit_sha() -> str:
    """Get the current Git commit SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def get_system_manifest(train_seeds: list[int], eval_seeds: list[int]) -> dict[str, Any]:
    """Capture environment, Git SHA, seed isolation policy, and hardware metadata."""
    return {
        "git_commit_sha": get_git_commit_sha(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "train_seeds": train_seeds,
        "eval_seeds": eval_seeds,
        "seed_isolation_policy": "strict_disjoint_train_eval_barrier",
        "benchmark_design": {
            "topologies": ["fat_tree", "scale_free"],
            "traffic_regimes": ["uniform", "hotspot"],
            "failure_conditions": ["nominal", "single_link_cut"],
            "valid_primary_algorithms": [
                "static_dijkstra",
                "dynamic_dijkstra",
                "ecmp",
                "ai_xgboost",
            ],
            "auxiliary_diagnostic_algorithms": ["rl_ppo"],
            "total_runs": 120,
        },
    }


def find_highest_betweenness_edge(topology: Topology) -> tuple[str, str]:
    """Find edge with highest edge betweenness centrality."""
    ebc = nx.edge_betweenness_centrality(topology.graph)
    if not ebc:
        edges = list(topology.edges)
        return (str(edges[0][0]), str(edges[0][1]))
    best_edge: Any = max(ebc, key=lambda k: float(ebc[k]))
    return (str(best_edge[0]), str(best_edge[1]))


def create_topology(topo_type: str, seed: int) -> Topology:
    """
    Instantiate calibrated topologies:
    - Fat-Tree (K=4, 36 nodes, 96 edges): host=8Mbps, pod=15Mbps, core=30Mbps
    - Scale-Free (50 nodes, 98 edges): default=10Mbps
    """
    if topo_type == "fat_tree":
        return TopologyGenerator.fat_tree(
            k=4,
            host_bandwidth=8.0,
            pod_bandwidth=15.0,
            core_bandwidth=30.0,
            seed=seed,
        )
    elif topo_type == "scale_free":
        return TopologyGenerator.scale_free(
            n_nodes=50,
            default_bandwidth=10.0,
            seed=seed,
        )
    else:
        raise ValueError(f"Unknown topology type: {topo_type}")


def pretrain_models_for_topology(
    topo_type: str,
    train_seed: int,
) -> tuple[AIRouter, RLRouter]:
    """
    Pretrain AIRouter and RLRouter on a distinct training topology instance
    using disjoint training seeds to prevent evaluation data leakage.
    """
    train_topo = create_topology(topo_type, seed=train_seed)

    # 1. Train AIRouter with comprehensive feature distribution spanning [0.0, 1.0]
    ai_router = AIRouter(
        topology=train_topo,
        congestion_model_type="xgboost",
        anomaly_model_type="isolation_forest",
        alpha=5.0,
    )
    rng = np.random.RandomState(train_seed)
    train_utils = rng.uniform(0.0, 1.0, 400)
    train_rows = []
    for u in train_utils:
        train_rows.append(
            {
                "bandwidth": 8.0 if rng.rand() > 0.5 else 15.0,
                "latency": 1.0 if rng.rand() > 0.5 else 2.0,
                "utilization_t": u,
                "neighbor_utilization_avg": u * 0.5,
                "utilization_t_1": u * 0.8,
                "utilization_t_2": u * 0.64,
                "utilization_t_3": u * 0.51,
                "utilization_t_4": u * 0.41,
                "utilization_t_5": u * 0.33,
            }
        )
    xgb_train_df = pd.DataFrame(train_rows)
    xgb_labels = (train_utils >= 0.70).astype(int)

    ai_router.train(
        features_congestion=xgb_train_df,
        labels_congestion=xgb_labels,
        features_anomaly=xgb_train_df,
        epochs=10,
    )

    # 2. Train RLRouter (PPO) for 1,000 episodes on training topology
    rl_router = RLRouter(topology=train_topo, algorithm="ppo", confidence_threshold=0.4)
    rl_router.train(episodes=1000, seed=train_seed)

    return ai_router, rl_router


def run_single_experiment(
    topo_type: str,
    traffic_model: str,
    failure_type: str,
    algorithm: str,
    eval_seed: int,
    train_seed: int,
    duration_ticks: int = 25,
    pretrained_ai: AIRouter | None = None,
    pretrained_rl: RLRouter | None = None,
) -> dict[str, Any]:
    """
    Execute a single isolated benchmark run and return comprehensive telemetry.
    """
    # 1. Create topology with evaluation seed
    topo = create_topology(topo_type, seed=eval_seed)

    # 2. Configure Failure Injector
    failure_injector: FailureInjector | None = None
    failure_tick: int | None = None
    recovery_tick: int | None = None

    if failure_type == "single_link_cut":
        failure_injector = FailureInjector()
        u, v = find_highest_betweenness_edge(topo)
        failure_tick = 10
        recovery_tick = 20
        failure_injector.schedule_link_failure(u, v, failure_tick)
        failure_injector.schedule_recovery(u, v, recovery_tick)

    # 3. Instantiate and instrument router
    raw_router: Any
    if algorithm == "static_dijkstra":
        raw_router = DijkstraRouter()
    elif algorithm == "dynamic_dijkstra":
        raw_router = DynamicDijkstraRouter(alpha=5.0)
    elif algorithm == "ecmp":
        raw_router = ECMPRouter()
    elif algorithm == "ai_xgboost":
        if pretrained_ai is not None:
            raw_router = pretrained_ai
        else:
            raw_router, _ = pretrain_models_for_topology(topo_type, train_seed)
        object.__setattr__(raw_router, "topology", topo)
    elif algorithm == "rl_ppo":
        if pretrained_rl is not None:
            raw_router = pretrained_rl
        else:
            _, raw_router = pretrain_models_for_topology(topo_type, train_seed)
        object.__setattr__(raw_router, "topology", topo)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    instrumented_router = InstrumentedRouter(raw_router)

    # 4. Configure Traffic Generator with evaluation seed
    n_flows = 20 if traffic_model == "hotspot" else 10
    traffic_gen = TrafficGenerator(model=traffic_model, n_flows_per_tick=n_flows, seed=eval_seed)

    # 5. Configure Simulation Engine and Metrics Recorder
    recorder = PilotMetricsRecorder(
        base_topology=topo,
        failure_tick=failure_tick,
        recovery_tick=recovery_tick,
    )

    engine = SimulationEngine(
        topology=topo,
        router=instrumented_router,
        traffic_generator=traffic_gen,
        failure_injector=failure_injector,
    )

    # Hook tick callback
    def on_tick_callback(tick: int, eng: SimulationEngine) -> None:
        recorder.on_tick(tick, eng)

    # 6. Execute Simulation Run
    engine.run(
        duration_ticks=duration_ticks,
        seed=eval_seed,
        callback=on_tick_callback,
        show_progress=False,
    )

    # 7. Collect and structure run results
    summary = recorder.compute_summary(instrumented_router)

    return {
        "run_id": f"{topo_type}_{traffic_model}_{failure_type}_{algorithm}_seed{eval_seed}",
        "topology_type": topo_type,
        "topology_nodes": topo.node_count,
        "topology_edges": topo.edge_count,
        "traffic_model": traffic_model,
        "failure_type": failure_type,
        "algorithm": algorithm,
        "track": "auxiliary_rl_diagnostic" if algorithm == "rl_ppo" else "primary_valid_candidate",
        "eval_seed": eval_seed,
        "train_seed": train_seed,
        "duration_ticks": duration_ticks,
        **summary,
    }


def run_full_pilot(output_dir: str = "artifacts") -> pd.DataFrame:
    """
    Execute the complete 120-run validation matrix across:
    2 Topologies x 2 Traffic x 2 Failures x 5 Algorithms x 3 Seeds = 120 runs.
    """
    topologies = ["fat_tree", "scale_free"]
    traffic_models = ["uniform", "hotspot"]
    failure_types = ["nominal", "single_link_cut"]
    algorithms = ["static_dijkstra", "dynamic_dijkstra", "ecmp", "ai_xgboost", "rl_ppo"]
    eval_seeds = [42, 43, 44]
    train_seeds = [1001, 1002, 1003]

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Save manifest
    manifest = get_system_manifest(train_seeds=train_seeds, eval_seeds=eval_seeds)
    with open(out_path / "benchmark_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Pretrain models for each topology to reuse across evaluation runs
    pretrain_cache: dict[str, tuple[AIRouter, RLRouter]] = {}
    for t in topologies:
        pretrain_cache[t] = pretrain_models_for_topology(t, train_seed=train_seeds[0])

    all_results: list[dict[str, Any]] = []

    for topo in topologies:
        ai_model, rl_model = pretrain_cache[topo]
        for traffic in traffic_models:
            for failure in failure_types:
                for algo in algorithms:
                    for s_idx, eval_seed in enumerate(eval_seeds):
                        train_seed = train_seeds[s_idx]

                        res = run_single_experiment(
                            topo_type=topo,
                            traffic_model=traffic,
                            failure_type=failure,
                            algorithm=algo,
                            eval_seed=eval_seed,
                            train_seed=train_seed,
                            duration_ticks=25,
                            pretrained_ai=ai_model if algo == "ai_xgboost" else None,
                            pretrained_rl=rl_model if algo == "rl_ppo" else None,
                        )
                        all_results.append(res)

    df = pd.DataFrame(all_results)
    df.to_csv(out_path / "benchmark_120_results.csv", index=False)
    df.to_json(out_path / "benchmark_120_results.json", orient="records", indent=2)
    return df
