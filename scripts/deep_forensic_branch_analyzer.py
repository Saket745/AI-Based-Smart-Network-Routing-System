"""Deep Forensic Diff & Content Analyzer for Unmerged Git Branches."""

import json
import subprocess
from pathlib import Path


def run_git(args: list[str]) -> str:
    res = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return res.stdout.strip()


def main():
    matrix = json.loads(Path("artifacts/branch_decision_matrix.json").read_text(encoding="utf-8"))

    unmerged_branches = [
        b for b in matrix if b["proposed_action"] in ("ARCHIVE_OR_DELETE", "EVALUATE_PR")
    ]
    print(f"Analyzing {len(unmerged_branches)} unmerged branches in detail...")

    detailed_reports = []

    for b in unmerged_branches:
        name = b["name"]
        clean_name = b.get("clean_name", name)
        ahead = b["ahead_main"]

        # Get diff summary against main
        try:
            _ = run_git(["diff", "--stat", f"main...{name}"])
            diff_files = run_git(["diff", "--name-only", f"main...{name}"]).splitlines()
        except Exception:
            diff_files = []

        # Get commits
        try:
            commits = run_git(["log", "--oneline", f"main..{name}"]).splitlines()
        except Exception:
            commits = []

        # Analyze nature of changes
        is_only_tests = all(f.startswith("tests/") for f in diff_files) if diff_files else False
        is_doc_only = all(f.endswith(".md") for f in diff_files) if diff_files else False
        touches_core = any(f.startswith("src/nroute/core/") for f in diff_files)
        touches_routing = any(f.startswith("src/nroute/routing/") for f in diff_files)
        touches_ml = any(f.startswith("src/nroute/ml/") for f in diff_files)
        touches_simulation = any(f.startswith("src/nroute/simulation/") for f in diff_files)
        touches_api = any(f.startswith("src/nroute/api/") for f in diff_files)
        touches_cli = any(f.startswith("src/nroute/cli/") for f in diff_files)

        detailed_reports.append(
            {
                "name": name,
                "clean_name": clean_name,
                "ahead": ahead,
                "behind": b["behind_main"],
                "open_pr": b.get("open_pr"),
                "commits": commits,
                "files_changed_count": len(diff_files),
                "files_changed": diff_files,
                "is_only_tests": is_only_tests,
                "is_doc_only": is_doc_only,
                "touches_core": touches_core,
                "touches_routing": touches_routing,
                "touches_ml": touches_ml,
                "touches_simulation": touches_simulation,
                "touches_api": touches_api,
                "touches_cli": touches_cli,
                "last_commit_author": b["last_commit_author"],
                "last_commit_date": b["last_commit_date"],
                "last_commit_subject": b["last_commit_subject"],
            }
        )

    out_path = Path("artifacts/unmerged_branches_detailed.json")
    out_path.write_text(json.dumps(detailed_reports, indent=2), encoding="utf-8")
    print(f"Saved detailed forensic analysis to {out_path}")


if __name__ == "__main__":
    main()
