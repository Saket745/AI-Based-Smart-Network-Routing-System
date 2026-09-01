"""Analyze open PRs and correlate with branch inventory."""

import json
from pathlib import Path

prs_raw_path = Path("C:/Users/91705/.gemini/antigravity-ide/brain/4634347a-8a3f-4ac7-beed-96852a4d7272/.system_generated/steps/817/output.txt")
prs = json.loads(prs_raw_path.read_text(encoding="utf-8"))

print(f"Total Open PRs on GitHub: {len(prs)}")

pr_branches = {}
for p in prs:
    b = p["head"]["ref"]
    pr_branches[b] = {
        "pr_number": p["number"],
        "title": p["title"],
        "created_at": p["created_at"],
        "updated_at": p["updated_at"],
        "author": p["user"]["login"],
        "head_sha": p["head"]["sha"],
        "body_preview": (p["body"] or "")[:100].replace("\n", " "),
    }

out_path = Path("artifacts/open_prs_inventory.json")
out_path.write_text(json.dumps(pr_branches, indent=2))
print(f"Open PRs inventory written to {out_path}")

# Load branch inventory
branch_inv_path = Path("artifacts/branch_forensic_inventory.json")
branch_inv = json.loads(branch_inv_path.read_text(encoding="utf-8"))

print(f"\nCorrelating with {len(branch_inv)} remote branches:")
pr_matched = 0
for b in branch_inv:
    bname = b["branch_name"]
    if bname in pr_branches:
        b["open_pr"] = pr_branches[bname]
        pr_matched += 1
    else:
        b["open_pr"] = None

print(f"Branches backing an open PR: {pr_matched}")
print(f"Branches with NO open PR: {len(branch_inv) - pr_matched}")

# Save updated inventory
branch_inv_path.write_text(json.dumps(branch_inv, indent=2))
