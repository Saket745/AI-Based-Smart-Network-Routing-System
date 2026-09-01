import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    branches = json.loads(Path("artifacts/unmerged_branches_detailed.json").read_text(encoding="utf-8"))

    with_prs = [b for b in branches if b["open_pr"] is not None]
    without_prs = [b for b in branches if b["open_pr"] is None]

    print(f"Total unmerged branches: {len(branches)}")
    print(f"  * With open PRs: {len(with_prs)}")
    print(f"  * Without open PRs (abandoned/stale agent branches): {len(without_prs)}")

    print("\n" + "=" * 80)
    print("OPEN PR BRANCHES (Total 28):")
    print("=" * 80)
    for b in with_prs:
        pr = b["open_pr"]
        print(f"PR #{pr['number']}: [{b['clean_name']}]")
        print(f"  Title:   {pr['title']}")
        print(f"  Author:  {pr['user']} | Created: {pr['created_at']}")
        print(f"  Ahead:   {b['ahead']} | Behind: {b['behind']}")
        print(f"  Files:   {len(b['files_changed'])} files changed ({', '.join(b['files_changed'][:3])})")
        print()

    print("\n" + "=" * 80)
    print("TOP AUTHORS OF UNMERGED BRANCHES WITHOUT PRS:")
    print("=" * 80)
    authors = {}
    for b in without_prs:
        a = b["last_commit_author"]
        authors[a] = authors.get(a, 0) + 1
    for a, count in sorted(authors.items(), key=lambda x: x[1], reverse=True):
        print(f"  * {a}: {count} branches")

    # Inspect if any unmerged branch without PR has unique source code changes (outside tests/docs)
    core_touching = [b for b in without_prs if b["touches_core"] or b["touches_routing"] or b["touches_simulation"] or b["touches_api"]]
    print(f"\nUnmerged branches without PRs that touch core/routing/simulation/api: {len(core_touching)}")
    for b in core_touching[:20]:
        print(f"  * {b['clean_name']} (ahead={b['ahead']}, behind={b['behind']}, author={b['last_commit_author']})")
        print(f"    Subject: {b['last_commit_subject']}")
        print(f"    Files:   {b['files_changed']}")


if __name__ == "__main__":
    main()
