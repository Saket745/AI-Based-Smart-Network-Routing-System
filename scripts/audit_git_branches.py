"""Comprehensive Git Branch Forensic Audit Script.

Analyzes:
  * All local and remote branches
  * Reachability and merge status relative to main
  * Unique commits on each branch
  * Commit classification and relevance
  * Deletion safety and preservation requirements
"""

import json
import subprocess
from pathlib import Path


def run_git(cmd: list[str]) -> str:
    """Run a git command and return stripped stdout."""
    res = subprocess.run(
        ["git"] + cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return res.stdout.strip()


def is_ancestor(commit: str, base: str = "main") -> bool:
    """Check if commit is an ancestor of base (i.e., fully merged)."""
    res = subprocess.run(["git", "merge-base", "--is-ancestor", commit, base])
    return res.returncode == 0


def audit_branches():
    # 1. Fetch remote branch list
    raw_branches = run_git(["branch", "-a"]).splitlines()
    local_branches = [b.strip().replace("* ", "") for b in run_git(["branch"]).splitlines()]
    
    remote_branches = []
    for line in raw_branches:
        line = line.strip()
        if line.startswith("remotes/origin/") and not line.startswith("remotes/origin/HEAD"):
            bname = line.replace("remotes/origin/", "")
            remote_branches.append(bname)

    print(f"Total Local Branches: {len(local_branches)}")
    print(f"Total Remote Branches: {len(remote_branches)}")

    inventory = []

    for b in remote_branches:
        ref = f"origin/{b}"
        merged = is_ancestor(ref, "main")
        
        # Ahead / Behind main
        ahead = int(run_git(["rev-list", "--count", f"main..{ref}"]))
        behind = int(run_git(["rev-list", "--count", f"{ref}..main"]))
        
        # Last commit metadata
        last_commit_info = run_git(
            ["log", "-1", "--format=%H|%an|%ad|%s", "--date=short", ref]
        ).split("|", 3)
        commit_hash, author, date, subject = (
            last_commit_info[0],
            last_commit_info[1],
            last_commit_info[2],
            last_commit_info[3] if len(last_commit_info) > 3 else "",
        )

        # Unique commits
        unique_commits = []
        if ahead > 0:
            raw_unique = run_git(["log", f"main..{ref}", "--format=%H|%s"]).splitlines()
            for u in raw_unique:
                if u.strip():
                    h, s = u.split("|", 1)
                    unique_commits.append({"hash": h, "subject": s})

        # Classification & Action
        if merged or ahead == 0:
            relevance = "Merged into main"
            action = "DELETE"
            reason = "All commits are already merged into main."
        else:
            # Analyze unmerged branch
            if "jules" in b or any(c.isdigit() and len(c) > 10 for c in b.split("-")):
                relevance = "Abandoned AI Agent / Automated branch"
                action = "DELETE" if "test" not in b else "REVIEW"
                reason = f"{ahead} unmerged commits from automated agent experiment."
            else:
                relevance = "Unmerged feature/fix branch"
                action = "REVIEW"
                reason = f"{ahead} unmerged commits require diff inspection."

        record = {
            "branch_name": b,
            "ref": ref,
            "merged": merged,
            "ahead_of_main": ahead,
            "behind_main": behind,
            "last_commit_hash": commit_hash,
            "author": author,
            "date": date,
            "subject": subject,
            "unique_commits": unique_commits,
            "relevance": relevance,
            "action": action,
            "reason": reason,
        }
        inventory.append(record)

    out_path = Path("artifacts/branch_forensic_inventory.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inventory, indent=2))
    print(f"Inventory written to {out_path} ({len(inventory)} branches audited)")

    # Print Summary stats
    merged_count = sum(1 for b in inventory if b["merged"])
    unmerged_count = sum(1 for b in inventory if not b["merged"])
    print(f"Merged Branches: {merged_count}")
    print(f"Unmerged Branches: {unmerged_count}")

    if unmerged_count > 0:
        print("\n--- UNMERGED BRANCHES ---")
        for b in inventory:
            if not b["merged"]:
                clean_subj = b["subject"].encode("ascii", "replace").decode("ascii")
                print(f" * {b['branch_name']}: {b['ahead_of_main']} commits ahead ({clean_subj})")


if __name__ == "__main__":
    audit_branches()
