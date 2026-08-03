#!/usr/bin/env python3
"""
Branch naming convention validator.
Enforces standard prefixes for branches to ensure governance compliance.
"""

import re
import sys
import subprocess

# Allowed branch prefixes based on Governance V2 Spec
ALLOWED_PREFIXES = [
    "feat/",
    "fix/",
    "perf/",
    "docs/",
    "refactor/",
    "ci/",
    "security/",
    "release/",
    "agent/",
    "hotfix/",
    "test/",
    "experiment/"
]

# Primary branches that are exempt
EXEMPT_BRANCHES = ["main", "dev", "master"]

def get_current_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return None

def validate_branch_name(branch_name):
    if not branch_name:
        return False, "Could not determine branch name."

    if branch_name in EXEMPT_BRANCHES:
        return True, ""

    # Check for conventional prefixes
    for prefix in ALLOWED_PREFIXES:
        if branch_name.startswith(prefix):
            return True, ""

    # Check for Jules-style branches (sometimes they are flat)
    if re.match(r"^jules-", branch_name):
        return True, ""

    return False, (
        f"Branch name '{branch_name}' does not follow convention.\n"
        f"Allowed prefixes: {', '.join(ALLOWED_PREFIXES)}\n"
        f"Exempt branches: {', '.join(EXEMPT_BRANCHES)}"
    )

def main():
    # If a branch name is passed as an argument, use it. Otherwise, use current branch.
    branch_name = sys.argv[1] if len(sys.argv) > 1 else get_current_branch()

    if not branch_name or branch_name == "HEAD":
        # In CI PR context, we might be in a detached HEAD state.
        # We should check the source branch of the PR.
        print("Detached HEAD or no branch specified. Skipping local branch validation.")
        return 0

    is_valid, error_msg = validate_branch_name(branch_name)

    if not is_valid:
        print(f"\n[BRANCH GOVERNANCE FAILURE] {error_msg}\n")
        return 1

    print(f"[BRANCH GOVERNANCE SUCCESS] Branch '{branch_name}' is valid.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
