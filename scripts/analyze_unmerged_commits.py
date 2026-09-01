"""Deep Forensic Analysis of Unmerged Commits and Branches."""

import json
import subprocess
from pathlib import Path


def run_git(cmd: list[str]) -> str:
    res = subprocess.run(
        ["git"] + cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return res.stdout.strip()


def analyze_unmerged():
    branch_inv_path = Path("artifacts/branch_forensic_inventory.json")
    branches = json.loads(branch_inv_path.read_text(encoding="utf-8"))

    unmerged = [b for b in branches if not b["merged"]]
    print(f"Total Unmerged Branches to Analyze: {len(unmerged)}")

    detailed_unmerged = []

    # Category buckets
    categories = {
        "jules_automated_agent": [],
        "automated_test_addition": [],
        "automated_refactor": [],
        "automated_security_fix": [],
        "automated_perf_optimization": [],
        "feature_proposal": [],
        "temp_or_conflict_resolution": [],
        "other": [],
    }

    for b in unmerged:
        name = b["branch_name"]
        ref = b["ref"]
        ahead = b["ahead_of_main"]
        behind = b["behind_main"]

        # Get diffstat relative to main
        try:
            diffstat = run_git(["diff", "--stat", f"main...{ref}"])
        except Exception:
            diffstat = "Error generating diffstat"

        # Unique commits list
        raw_commits = run_git(["log", f"main..{ref}", "--format=%H|%an|%ad|%s", "--date=short"]).splitlines()
        commits = []
        for c in raw_commits:
            parts = c.split("|", 3)
            commits.append({
                "hash": parts[0],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3] if len(parts) > 3 else "",
            })

        # Categorize
        if name.startswith("agent/") or "jules" in name or name.startswith("jules-"):
            cat = "jules_automated_agent"
        elif name.startswith("test/") or name.startswith("test-") or name.startswith("testing-") or name.startswith("testing/"):
            cat = "automated_test_addition"
        elif name.startswith("refactor/") or name.startswith("refactor-"):
            cat = "automated_refactor"
        elif name.startswith("security/") or name.startswith("security-") or name.startswith("sentinel-") or name.startswith("sentinel/"):
            cat = "automated_security_fix"
        elif name.startswith("perf/") or name.startswith("performance/"):
            cat = "automated_perf_optimization"
        elif name.startswith("feature/") or name.startswith("feat/") or name.startswith("feat-"):
            cat = "feature_proposal"
        elif "temp" in name or "tmp" in name or "conflict" in name or "revert" in name:
            cat = "temp_or_conflict_resolution"
        else:
            cat = "other"

        categories[cat].append(name)

        record = {
            "branch_name": name,
            "category": cat,
            "ahead_of_main": ahead,
            "behind_main": behind,
            "open_pr": b.get("open_pr"),
            "diffstat_lines": len(diffstat.splitlines()),
            "diffstat_summary": diffstat.splitlines()[-1] if diffstat.splitlines() else "",
            "unique_commits": commits,
        }
        detailed_unmerged.append(record)

    out_path = Path("artifacts/unmerged_forensic_report.json")
    out_path.write_text(json.dumps(detailed_unmerged, indent=2))
    print(f"Report written to {out_path}")

    print("\n--- CATEGORY BREAKDOWN OF 214 UNMERGED BRANCHES ---")
    for cat, blist in categories.items():
        print(f" * {cat}: {len(blist)} branches")


if __name__ == "__main__":
    analyze_unmerged()
