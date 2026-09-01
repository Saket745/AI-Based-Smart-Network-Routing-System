"""Statistical analysis script for 120-run Phase-1 Benchmark."""

import numpy as np
import pandas as pd
from scipy import stats

df = pd.read_csv("artifacts/benchmark_120_results.csv")
print(f"Total rows loaded: {len(df)}")

primary_df = df[df["track"] == "primary_valid_candidate"]
aux_df = df[df["track"] == "auxiliary_rl_diagnostic"]
print(f"Primary runs: {len(primary_df)}, Auxiliary runs: {len(aux_df)}")


def cohen_d_ci(x, y):
    nx, ny = len(x), len(y)
    pooled_sd = np.sqrt(
        ((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / (nx + ny - 2)
    )
    d = (np.mean(x) - np.mean(y)) / pooled_sd if pooled_sd > 0 else 0.0
    se = np.sqrt((nx + ny) / (nx * ny) + (d**2) / (2 * (nx + ny)))
    ci_low = d - 1.96 * se
    ci_high = d + 1.96 * se
    return d, ci_low, ci_high


comparisons = [
    ("ai_xgboost", "static_dijkstra"),
    ("ai_xgboost", "dynamic_dijkstra"),
    ("dynamic_dijkstra", "static_dijkstra"),
    ("ecmp", "static_dijkstra"),
]

print("\n=== OVERALL PRIMARY TRACK COMPARISONS (N=24 runs per algorithm) ===")
for a1, a2 in comparisons:
    sub1 = primary_df[primary_df["algorithm"] == a1]
    sub2 = primary_df[primary_df["algorithm"] == a2]

    for metric in [
        "mean_latency_ms",
        "mean_peak_utilization",
        "mean_path_stretch",
        "mean_compute_latency_us",
    ]:
        v1 = sub1[metric].values
        v2 = sub2[metric].values
        m1, s1 = np.mean(v1), np.std(v1, ddof=1)
        m2, s2 = np.mean(v2), np.std(v2, ddof=1)
        d, ci_l, ci_h = cohen_d_ci(v1, v2)
        t_stat, p_val = stats.ttest_rel(v1, v2) if len(v1) == len(v2) else (0.0, 1.0)
        print(f"{a1} vs {a2} | {metric}:")
        print(f"  {a1}: {m1:.4f} +/- {s1:.4f} | {a2}: {m2:.4f} +/- {s2:.4f}")
        print(
            f"  Diff: {m1 - m2:+.4f} | Cohen d: {d:+.3f} (95% CI: [{ci_l:+.3f}, {ci_h:+.3f}]) | paired-t: p={p_val:.4e}"
        )

print("\n=== BREAKDOWN BY TOPOLOGY ===")
for topo in ["fat_tree", "scale_free"]:
    t_df = primary_df[primary_df["topology_type"] == topo]
    print(f"\n-- Topology: {topo} --")
    for algo in ["static_dijkstra", "dynamic_dijkstra", "ecmp", "ai_xgboost"]:
        sub = t_df[t_df["algorithm"] == algo]
        lat = sub["mean_latency_ms"].mean()
        p95 = sub["p95_latency_ms"].mean()
        peak = sub["mean_peak_utilization"].mean() * 100
        stretch = sub["mean_path_stretch"].mean()
        comp = sub["mean_compute_latency_us"].mean()
        churn = sub["route_churn_rate"].mean()
        print(
            f"  {algo:16s} | Lat: {lat:.3f} ms | P95: {p95:.3f} ms | Peak: {peak:.1f}% | Stretch: {stretch:.3f} | Churn: {churn:.4f} | Comp: {comp:.1f} us"
        )

print("\n=== BREAKDOWN BY TRAFFIC REGIME ===")
for traffic in ["uniform", "hotspot"]:
    tr_df = primary_df[primary_df["traffic_model"] == traffic]
    print(f"\n-- Traffic: {traffic} --")
    for algo in ["static_dijkstra", "dynamic_dijkstra", "ecmp", "ai_xgboost"]:
        sub = tr_df[tr_df["algorithm"] == algo]
        lat = sub["mean_latency_ms"].mean()
        p95 = sub["p95_latency_ms"].mean()
        peak = sub["mean_peak_utilization"].mean() * 100
        stretch = sub["mean_path_stretch"].mean()
        comp = sub["mean_compute_latency_us"].mean()
        churn = sub["route_churn_rate"].mean()
        print(
            f"  {algo:16s} | Lat: {lat:.3f} ms | P95: {p95:.3f} ms | Peak: {peak:.1f}% | Stretch: {stretch:.3f} | Churn: {churn:.4f} | Comp: {comp:.1f} us"
        )

print("\n=== BREAKDOWN BY FAILURE CONDITION ===")
for fail in ["nominal", "single_link_cut"]:
    f_df = primary_df[primary_df["failure_type"] == fail]
    print(f"\n-- Failure: {fail} --")
    for algo in ["static_dijkstra", "dynamic_dijkstra", "ecmp", "ai_xgboost"]:
        sub = f_df[f_df["algorithm"] == algo]
        lat = sub["mean_latency_ms"].mean()
        p95 = sub["p95_latency_ms"].mean()
        peak = sub["mean_peak_utilization"].mean() * 100
        stretch = sub["mean_path_stretch"].mean()
        comp = sub["mean_compute_latency_us"].mean()
        churn = sub["route_churn_rate"].mean()
        print(
            f"  {algo:16s} | Lat: {lat:.3f} ms | P95: {p95:.3f} ms | Peak: {peak:.1f}% | Stretch: {stretch:.3f} | Churn: {churn:.4f} | Comp: {comp:.1f} us"
        )

print("\n=== AUXILIARY TRACK: RL-PPO DIAGNOSTICS (N=24 runs) ===")
rl_df = aux_df[aux_df["algorithm"] == "rl_ppo"]
print(
    f"Mean Fallback Ratio: {rl_df['fallback_ratio'].mean() * 100:.1f}% (Min: {rl_df['fallback_ratio'].min() * 100:.1f}%, Max: {rl_df['fallback_ratio'].max() * 100:.1f}%)"
)
print(f"Mean Compute Latency: {rl_df['mean_compute_latency_us'].mean():.1f} us")
for topo in ["fat_tree", "scale_free"]:
    sub = rl_df[rl_df["topology_type"] == topo]
    print(
        f"  Topology {topo:10s} | Fallback Ratio: {sub['fallback_ratio'].mean() * 100:.1f}% | Compute: {sub['mean_compute_latency_us'].mean():.1f} us"
    )
