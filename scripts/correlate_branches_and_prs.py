"""Correlate Git Branches with GitHub PRs, Actions, and Workflows."""

import json
from pathlib import Path


def main():
    # 1. Load branches audit
    branch_inventory = json.loads(Path("artifacts/branch_forensic_inventory.json").read_text(encoding="utf-8"))

    # 2. Load open PRs from the step output
    # Find step 801 output file
    step_file = list(Path(r"C:\Users\91705\.gemini\antigravity-ide\brain\4634347a-8a3f-4ac7-beed-96852a4d7272\.system_generated\steps").glob("*/output.txt"))
    open_prs = []
    for sf in step_file:
        try:
            content = sf.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, list) and len(data) > 0 and "html_url" in data[0]:
                open_prs = data
                break
        except Exception:
            continue

    print(f"Total open PRs discovered: {len(open_prs)}")

    pr_by_branch = {}
    for pr in open_prs:
        ref = pr.get("head", {}).get("ref", "")
        pr_by_branch[ref] = {
            "number": pr["number"],
            "title": pr["title"],
            "url": pr["html_url"],
            "created_at": pr["created_at"],
            "user": pr.get("user", {}).get("login", ""),
            "base_ref": pr.get("base", {}).get("ref", ""),
        }

    # Analyze categories
    categories = {
        "jules_agent": 0,
        "security_patches": 0,
        "testing_improvements": 0,
        "refactoring": 0,
        "features": 0,
        "other": 0,
    }

    annotated_branches = []
    for b in branch_inventory:
        c_name = b.get("clean_name", b["name"])
        pr_info = pr_by_branch.get(c_name)
        b["open_pr"] = pr_info

        # Categorize
        if any(x in c_name for x in ["jules", "agent/", "task-", "-6", "-1", "-2", "-3", "-4", "-5", "-7", "-8", "-9"]) and len(c_name.split("-")[-1]) >= 18:
            cat = "jules_automated_task"
        elif c_name.startswith("security/") or "security" in c_name or "sentinel" in c_name:
            cat = "security"
        elif c_name.startswith("test") or "coverage" in c_name:
            cat = "testing"
        elif c_name.startswith("refactor/"):
            cat = "refactoring"
        elif c_name.startswith("feat/"):
            cat = "feature"
        elif c_name.startswith("fix/"):
            cat = "bugfix"
        elif c_name == "main":
            cat = "main"
        else:
            cat = "other"

        b["category"] = cat

        # Determine Recommendation:
        if c_name == "main":
            action = "KEEP"
            reason = "Authoritative primary branch"
        elif b["is_merged_to_main"]:
            action = "DELETE"
            reason = "Already fully merged into main (0 ahead commits)"
        elif b["ahead_main"] == 0:
            action = "DELETE"
            reason = "Ancestral subset of main (0 unique commits)"
        else:
            # Has unique commits
            if pr_info is not None:
                action = "EVALUATE_PR"
                reason = f"Open PR #{pr_info['number']}: {pr_info['title']}"
            else:
                action = "ARCHIVE_OR_DELETE"
                reason = f"Unmerged branch with {b['ahead_main']} commits ahead, {b['behind_main']} commits behind main"

        b["proposed_action"] = action
        b["action_reason"] = reason
        annotated_branches.append(b)

    out_file = Path("artifacts/branch_decision_matrix.json")
    out_file.write_text(json.dumps(annotated_branches, indent=2), encoding="utf-8")
    print(f"Saved annotated branch decision matrix to {out_file}")

    # Summary statistics
    actions_count = {}
    for b in annotated_branches:
        act = b["proposed_action"]
        actions_count[act] = actions_count.get(act, 0) + 1

    print("\nProposed Actions Breakdown:")
    for act, count in actions_count.items():
        print(f"  * {act}: {count}")


if __name__ == "__main__":
    main()
