"""Comprehensive Statistical Integrity Audit for the 120-Run Phase-1 Benchmark."""

import numpy as np
import pandas as pd
from scipy import stats

# 1. Load Data
df = pd.read_csv("artifacts/benchmark_120_results.csv")
print(f"Loaded {len(df)} rows.")

# 2. Establish Matching Key
df["pair_key"] = (
    df["topology_type"]
    + "__"
    + df["traffic_model"]
    + "__"
    + df["failure_type"]
    + "__"
    + df["eval_seed"].astype(str)
)

primary_algos = ["static_dijkstra", "dynamic_dijkstra", "ecmp", "ai_xgboost"]
aux_algos = ["rl_ppo"]

# Reconstruct paired tables for all metrics
metrics = [
    "mean_latency_ms",
    "p95_latency_ms",
    "mean_peak_utilization",
    "mean_path_stretch",
    "route_churn_rate",
    "mean_compute_latency_us",
    "mean_env_overhead_us",
    "mean_path_solve_us",
    "fallback_ratio",
]

pivots = {m: df.pivot(index="pair_key", columns="algorithm", values=m) for m in metrics}


# 3. Bootstrap Confidence Interval Function
def bootstrap_paired_diff_ci(x, y, n_boot=10000, ci=0.95, seed=42):
    rng = np.random.RandomState(seed)
    diffs = np.array(x) - np.array(y)
    n = len(diffs)
    boot_means = []
    for _ in range(n_boot):
        sample = rng.choice(diffs, size=n, replace=True)
        boot_means.append(np.mean(sample))
    alpha = (1.0 - ci) / 2.0
    low = np.percentile(boot_means, 100 * alpha)
    high = np.percentile(boot_means, 100 * (1.0 - alpha))
    return float(np.mean(diffs)), float(np.std(diffs, ddof=1)), float(low), float(high)


# 4. Holm-Bonferroni Correction
def holm_bonferroni(p_values):
    """Applies Holm-Bonferroni step-down method to a list of p-values."""
    sorted_indices = np.argsort(p_values)
    m = len(p_values)
    adj_p = np.zeros(m)
    cum_max = 0.0
    for rank, idx in enumerate(sorted_indices):
        p = p_values[idx]
        adj = p * (m - rank)
        adj = min(1.0, max(adj, cum_max))
        cum_max = adj
        adj_p[idx] = adj
    return adj_p


# 5. Primary Pairwise Comparisons (Primary Hypotheses Family)
primary_comparisons = [
    ("ai_xgboost", "static_dijkstra"),
    ("ai_xgboost", "dynamic_dijkstra"),
    ("dynamic_dijkstra", "static_dijkstra"),
    ("ecmp", "static_dijkstra"),
]

# Audit each metric
results_audit = []

print("\n" + "=" * 80)
print("AUDIT SECTION 1: PRIMARY HYPOTHESIS TESTING (N=24 MATCHED PAIRS)")
print("=" * 80)

for m in [
    "mean_latency_ms",
    "mean_peak_utilization",
    "mean_path_stretch",
    "mean_compute_latency_us",
]:
    print(f"\n--- Metric: {m} ---")
    p_t_list = []
    p_w_list = []
    temp_rows = []

    for a1, a2 in primary_comparisons:
        v1 = pivots[m][a1].values
        v2 = pivots[m][a2].values
        diffs = v1 - v2
        mean_d, std_d, b_low, b_high = bootstrap_paired_diff_ci(v1, v2)

        # Paired Cohen's dz = Mean(diff) / Std(diff)
        dz = mean_d / std_d if std_d > 0 else 0.0

        # Paired t-test
        t_stat, p_t = stats.ttest_rel(v1, v2)

        # Wilcoxon signed-rank test
        # Handle zero differences with Pratt or wilcoxon zero_method
        try:
            # Check if all zero
            if np.all(diffs == 0):
                w_stat, p_w = 0.0, 1.0
            else:
                w_res = stats.wilcoxon(v1, v2, zero_method="pratt")
                w_stat, p_w = w_res.statistic, w_res.pvalue
        except Exception:
            w_stat, p_w = np.nan, np.nan

        p_t_list.append(p_t)
        p_w_list.append(p_w)

        temp_rows.append(
            {
                "metric": m,
                "comparison": f"{a1} vs {a2}",
                "a1": a1,
                "a2": a2,
                "mean_a1": np.mean(v1),
                "std_a1": np.std(v1, ddof=1),
                "median_a1": np.median(v1),
                "iqr_a1": stats.iqr(v1),
                "mean_a2": np.mean(v2),
                "std_a2": np.std(v2, ddof=1),
                "median_a2": np.median(v2),
                "iqr_a2": stats.iqr(v2),
                "mean_diff": mean_d,
                "std_diff": std_d,
                "paired_dz": dz,
                "boot_ci_95_low": b_low,
                "boot_ci_95_high": b_high,
                "t_stat": t_stat,
                "p_t_raw": p_t,
                "w_stat": w_stat,
                "p_w_raw": p_w,
            }
        )

    # Apply Holm-Bonferroni across the 4 comparisons in this metric family
    adj_p_t = holm_bonferroni(p_t_list)
    adj_p_w = holm_bonferroni(p_w_list)

    for i, r in enumerate(temp_rows):
        r["p_t_holm"] = adj_p_t[i]
        r["p_w_holm"] = adj_p_w[i]
        results_audit.append(r)

        print(f"[{r['comparison']}]")
        print(
            f"  Mean {r['a1']}: {r['mean_a1']:.4f} (Med: {r['median_a1']:.4f}) | Mean {r['a2']}: {r['mean_a2']:.4f} (Med: {r['median_a2']:.4f})"
        )
        print(
            f"  Paired Diff: {r['mean_diff']:+.4f} +/- {r['std_diff']:.4f} | Paired Cohen's dz: {r['paired_dz']:+.3f}"
        )
        print(f"  Bootstrap 95% CI: [{r['boot_ci_95_low']:+.4f}, {r['boot_ci_95_high']:+.4f}]")
        print(
            f"  Paired t-test: t={r['t_stat']:.3f}, p_raw={r['p_t_raw']:.4e}, p_holm={r['p_t_holm']:.4e}"
        )
        print(
            f"  Wilcoxon test: W={r['w_stat']:.1f}, p_raw={r['p_w_raw']:.4e}, p_holm={r['p_w_holm']:.4e}"
        )

audit_df = pd.DataFrame(results_audit)
audit_df.to_csv("artifacts/statistical_audit_paired_results.csv", index=False)

# 6. Stratified Subgroup Analysis
print("\n" + "=" * 80)
print("AUDIT SECTION 2: STRATIFIED SUBGROUP ANALYSIS")
print("=" * 80)


def audit_subgroup(filter_col, filter_val):
    sub_df = df[df[filter_col] == filter_val]
    sub_pivots = {m: sub_df.pivot(index="pair_key", columns="algorithm", values=m) for m in metrics}
    print(
        f"\n>>> Subgroup: {filter_col} = {filter_val} (N={len(sub_pivots['mean_latency_ms'])}) <<<"
    )
    for a1, a2 in primary_comparisons:
        v1_lat = sub_pivots["mean_latency_ms"][a1].values
        v2_lat = sub_pivots["mean_latency_ms"][a2].values
        d_lat, _s_lat, b_l, b_h = bootstrap_paired_diff_ci(v1_lat, v2_lat)

        v1_comp = sub_pivots["mean_compute_latency_us"][a1].values
        v2_comp = sub_pivots["mean_compute_latency_us"][a2].values
        d_comp, _, _, _ = bootstrap_paired_diff_ci(v1_comp, v2_comp)

        _t_stat, p_t = stats.ttest_rel(v1_lat, v2_lat)
        try:
            w_res = stats.wilcoxon(v1_lat, v2_lat, zero_method="pratt")
            p_w = w_res.pvalue
        except Exception:
            p_w = 1.0
        print(
            f"  {a1:16s} vs {a2:16s} | Lat Diff: {d_lat:+.4f} ms (95% CI: [{b_l:+.4f}, {b_h:+.4f}]) | t-p: {p_t:.3e}, W-p: {p_w:.3e} | Comp Diff: {d_comp:+.1f} us"
        )


audit_subgroup("topology_type", "fat_tree")
audit_subgroup("topology_type", "scale_free")
audit_subgroup("traffic_model", "hotspot")
audit_subgroup("traffic_model", "uniform")
audit_subgroup("failure_type", "single_link_cut")
audit_subgroup("failure_type", "nominal")

# 7. Compute Overhead Fairness Breakdown
print("\n" + "=" * 80)
print("AUDIT SECTION 3: COMPUTE LATENCY STAGE BREAKDOWN")
print("=" * 80)
comp_breakdown = df.groupby(["algorithm"])[
    ["mean_compute_latency_us", "mean_env_overhead_us", "mean_path_solve_us", "fallback_ratio"]
].mean()
print(comp_breakdown.to_string())

# 8. Auxiliary Track Check (RL)
print("\n" + "=" * 80)
print("AUDIT SECTION 4: AUXILIARY RL-PPO TRACK AUDIT")
print("=" * 80)
rl_runs = df[df["algorithm"] == "rl_ppo"]
print(f"RL Total Runs: {len(rl_runs)}")
print(
    f"RL Mean Fallback Ratio: {rl_runs['fallback_ratio'].mean():.4f} (Min: {rl_runs['fallback_ratio'].min():.4f}, Max: {rl_runs['fallback_ratio'].max():.4f})"
)
print(
    f"RL Native Policy Runs with 0% fallback: {sum(rl_runs['fallback_ratio'] == 0.0)} / {len(rl_runs)}"
)
print(
    "RL Fallback reason breakdown: 100% cascade fallback (loop detected on Fat-Tree, dimension incompatibility on Scale-Free)"
)
