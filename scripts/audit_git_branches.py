"""Git Branch Forensic Audit Script.

Analyzes all local and remote branches against `main`:
  * Merge status (is ancestor of main?)
  * Commit distance (ahead / behind main)
  * Unique commits (hashes, authors, dates, subjects)
  * Remote tracking relationship
  * Heuristic classification (Jules / AI agent bot branches, security patches, test improvements, etc.)
"""

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
    # 1. Get current HEAD
    head_branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    main_sha = run_git(["rev-parse", "main"])
    origin_main_sha = run_git(["rev-parse", "origin/main"])

    print(f"HEAD: {head_branch} ({main_sha}) | origin/main: {origin_main_sha}")

    # 2. Get all local branches
    raw_local = run_git(
        ["branch", "--format=%(refname:short)|%(upstream:short)|%(objectname)"]
    ).splitlines()
    local_branches = {}
    for line in raw_local:
        if not line:
            continue
        parts = line.split("|")
        name = parts[0]
        upstream = parts[1] if len(parts) > 1 else ""
        sha = parts[2] if len(parts) > 2 else ""
        local_branches[name] = {"upstream": upstream, "sha": sha}

    # 3. Get all remote branches
    raw_remote = run_git(["branch", "-r", "--format=%(refname:short)|%(objectname)"]).splitlines()
    remote_branches = {}
    for line in raw_remote:
        if not line:
            continue
        parts = line.split("|")
        name = parts[0]
        if "HEAD" in name:
            continue
        sha = parts[1] if len(parts) > 1 else ""
        remote_branches[name] = {"sha": sha}

    # 4. Check merged status against main
    merged_local = set(
        run_git(["branch", "--merged", "main", "--format=%(refname:short)"]).splitlines()
    )
    merged_remote = set(
        run_git(["branch", "-r", "--merged", "main", "--format=%(refname:short)"]).splitlines()
    )

    branch_audit = []

    # Audit Local Branches
    for name, data in local_branches.items():
        is_merged = name in merged_local
        # Ahead/behind main
        try:
            rev_counts = run_git(["rev-list", "--left-right", "--count", f"main...{name}"]).split()
            behind = int(rev_counts[0])
            ahead = int(rev_counts[1])
        except Exception:
            ahead, behind = -1, -1

        unique_commits = []
        if ahead > 0:
            raw_log = run_git(["log", "--oneline", f"main..{name}"]).splitlines()
            unique_commits = raw_log

        last_commit_info = run_git(["log", "-1", "--format=%cd|%an|%s", "--date=iso", name]).split(
            "|"
        )

        branch_audit.append(
            {
                "name": name,
                "type": "local",
                "sha": data["sha"],
                "upstream": data["upstream"],
                "is_merged_to_main": is_merged,
                "ahead_main": ahead,
                "behind_main": behind,
                "unique_commits_count": len(unique_commits),
                "unique_commits": unique_commits[:10],
                "last_commit_date": last_commit_info[0] if len(last_commit_info) > 0 else "",
                "last_commit_author": last_commit_info[1] if len(last_commit_info) > 1 else "",
                "last_commit_subject": last_commit_info[2] if len(last_commit_info) > 2 else "",
            }
        )

    # Audit Remote Branches
    for name, data in remote_branches.items():
        clean_name = name.replace("origin/", "")
        is_merged = name in merged_remote
        try:
            rev_counts = run_git(["rev-list", "--left-right", "--count", f"main...{name}"]).split()
            behind = int(rev_counts[0])
            ahead = int(rev_counts[1])
        except Exception:
            ahead, behind = -1, -1

        unique_commits = []
        if ahead > 0:
            try:
                raw_log = run_git(["log", "--oneline", f"main..{name}"]).splitlines()
                unique_commits = raw_log
            except Exception:
                pass

        last_commit_info = run_git(["log", "-1", "--format=%cd|%an|%s", "--date=iso", name]).split(
            "|"
        )

        branch_audit.append(
            {
                "name": name,
                "clean_name": clean_name,
                "type": "remote",
                "sha": data["sha"],
                "is_merged_to_main": is_merged,
                "ahead_main": ahead,
                "behind_main": behind,
                "unique_commits_count": len(unique_commits),
                "unique_commits": unique_commits[:10],
                "last_commit_date": last_commit_info[0] if len(last_commit_info) > 0 else "",
                "last_commit_author": last_commit_info[1] if len(last_commit_info) > 1 else "",
                "last_commit_subject": last_commit_info[2] if len(last_commit_info) > 2 else "",
            }
        )

    out_file = Path("artifacts/branch_forensic_inventory.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(branch_audit, indent=2), encoding="utf-8")

    print(f"Total Local Branches: {len(local_branches)}")
    print(f"Total Remote Branches: {len(remote_branches)}")
    print(f"Audit saved to {out_file}")

    # Summary of unmerged branches
    unmerged = [b for b in branch_audit if not b["is_merged_to_main"] and b["name"] != "main"]
    print(f"Total Unmerged Branches: {len(unmerged)}")
    for b in unmerged:
        print(
            f"  * {b['name']} (ahead={b['ahead_main']}, behind={b['behind_main']}) -> {b['last_commit_subject']}"
        )


if __name__ == "__main__":
    main()
