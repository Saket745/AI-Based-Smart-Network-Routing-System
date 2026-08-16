#!/usr/bin/env python3
"""
Commit message validator hook.
Enforces Conventional Commits style guide for git commits.
"""

import re
import sys
from pathlib import Path

# Conventional commit types
VALID_TYPES = {
    "feat",
    "feature",
    "fix",
    "bugfix",
    "docs",
    "style",
    "refactor",
    "perf",
    "performance",  # Code changes that improve performance
    "test",  # Adding missing tests or correcting existing tests
    "build",  # Build system/dependency changes
    "ci",  # CI configurations and scripts
    "chore",  # Maintenance tasks
    "revert",  # Revert a previous commit
    "security",  # Security fixes
    "daily",  # Daily repository health audits / governance work
    "resolve",  # Security fixes
=======
    "performance",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
    "security",
    "daily",
    "resolve",
}

CONVENTIONAL_REGEX = re.compile(
    r"^(?:\W+\s*)?(?P<type>[a-zA-Z]+)(?:\((?P<scope>[a-zA-Z0-9_\-\/]+)\))?(?P<breaking>!)?:?\s+(?P<desc>.+)$"
)


def validate_message(msg: str) -> list[str]:
    """Validate a commit message. Returns a list of error messages, empty if valid."""
    errors = []
    msg = msg.strip()
    if not msg:
        return ["Commit message cannot be empty."]

    first_line = msg.splitlines()[0].strip() if msg.splitlines() else ""

    if (
        first_line.startswith("Merge branch")
        or first_line.startswith("Merge pull request")
        or first_line.startswith("Merge remote-tracking branch")
        or first_line.startswith('Revert "')
        or first_line.lower().startswith("wip")
        or first_line.lower().startswith("temp")
        or first_line.startswith("fixup!")
        or first_line.startswith("squash!")
        or first_line.startswith("Resolve Merge Conflict Syntax Errors")
        or re.match(r"^Merge [0-9a-fA-F]{7,40} into [0-9a-fA-F]{7,40}$", first_line)
    ):
        return []

    match = CONVENTIONAL_REGEX.match(first_line)
    if not match:
        errors.append(
            f"Commit header does not match Conventional Commits format.\n"
            f"  Current header: '{first_line}'\n"
            f"  Expected format: <type>(<scope>): <description>\n"
            f"  Allowed types: {', '.join(sorted(list(VALID_TYPES)))}"
        )
        return errors

    commit_type = match.group("type").lower()
    if commit_type not in VALID_TYPES:
        errors.append(
            f"Commit type '{commit_type}' is invalid.\n"
            f"  Allowed types: {', '.join(sorted(list(VALID_TYPES)))}"
        )

    desc = match.group("desc")
    if len(desc) < 5:
        errors.append("Commit description is too short (minimum 5 characters).")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_commit_msg.py <commit_msg_file_path_or_text>")
        return 1

    target = sys.argv[1]
    target_path = Path(target)
    try:
        is_file = target_path.is_file()
    except OSError:
        is_file = False

    if is_file:
        try:
            commit_msg = target_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading commit message file: {e}")
            return 1
    else:
        commit_msg = target

    errors = validate_message(commit_msg)

    if errors:
        print("\n[COMMIT GOVERNANCE FAILURE] Invalid commit message structure:\n")
        for err in errors:
            print(f"  - {err}")
        print("\nExamples of valid commit messages:")
        print("  feat(routing): implement shortest path strategy")
        print("  fix(simulation): resolve packet latency calculation")
        print("  docs(readme): update installation guide\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
