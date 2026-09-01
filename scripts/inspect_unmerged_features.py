"""Inspect feature proposals and other unmerged branches."""

import json
from pathlib import Path

report = json.loads(Path("artifacts/unmerged_forensic_report.json").read_text(encoding="utf-8"))

print("=== FEATURE PROPOSALS & OTHER UNMERGED BRANCHES ===")
for b in report:
    if b["category"] in ("feature_proposal", "other"):
        pr_info = f" [PR #{b['open_pr']['pr_number']}: {b['open_pr']['title']}]" if b["open_pr"] else " [NO PR]"
        header = f"\nBranch: {b['branch_name']}{pr_info}".encode("ascii", "replace").decode("ascii")
        print(header)
        print(f"  Ahead: {b['ahead_of_main']}, Behind: {b['behind_main']}")
        print(f"  Diff summary: {b['diffstat_summary']}")
        print("  Commits:")
        for c in b["unique_commits"][:3]:
            line = f"    - {c['hash'][:8]} {c['date']} ({c['author']}): {c['subject'][:70]}".encode("ascii", "replace").decode("ascii")
            print(line)
        if len(b["unique_commits"]) > 3:
            print(f"    ... and {len(b['unique_commits']) - 3} more")
