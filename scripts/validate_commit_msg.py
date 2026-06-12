#!/usr/bin/env python3
"""
Commit message validator hook.
Enforces Conventional Commits style guide for git commits.
"""

import sys
import re
from pathlib import Path

# Conventional commit types
VALID_TYPES = {
    "feat",     # New feature
    "fix",      # Bug fix
    "docs",     # Documentation changes
    "style",    # Formatting, missing semi-colons, etc (no code changes)
    "refactor", # Refactoring production code (e.g. renaming a variable)
    "perf",     # Code changes that improve performance
    "test",     # Adding missing tests or correcting existing tests
    "build",    # Build system/dependency changes
    "ci",       # CI configurations and scripts
    "chore",    # Maintenance tasks
    "revert",   # Revert a previous commit
}

# Regex to match conventional commits header
# Pattern: type(scope)!: Description
CONVENTIONAL_REGEX = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-zA-Z0-9_\-\/]+)\))?(?P<breaking>!)?:\s+(?P<desc>.+)$"
)

def validate_message(msg: str) -> list[str]:
    """Validate a commit message. Returns a list of error messages, empty if valid."""
    errors = []
    
    # Strip whitespace
    msg = msg.strip()
    if not msg:
        return ["Commit message cannot be empty."]

    # Ignore standard git merge or auto-generated commits
    if msg.startswith("Merge branch") or msg.startswith("Merge pull request") or msg.startswith("Merge remote-tracking branch"):
        return []

    # Get the first line (header) of the commit message
    first_line = msg.splitlines()[0].strip()

    match = CONVENTIONAL_REGEX.match(first_line)
    if not match:
        errors.append(
            f"Commit header does not match Conventional Commits format.\n"
            f"  Current header: '{first_line}'\n"
            f"  Expected format: <type>(<scope>): <description>\n"
            f"  Allowed types: {', '.join(sorted(list(VALID_TYPES)))}"
        )
        return errors

    # Check commit type
    commit_type = match.group("type")
    if commit_type not in VALID_TYPES:
        errors.append(
            f"Commit type '{commit_type}' is invalid.\n"
            f"  Allowed types: {', '.join(sorted(list(VALID_TYPES)))}"
        )

    # Check description format (minimum length, lowercase recommendation, etc.)
    desc = match.group("desc")
    if len(desc) < 5:
        errors.append("Commit description is too short (minimum 5 characters).")

    return errors

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_commit_msg.py <commit_msg_file_path_or_text>")
        return 1

    target = sys.argv[1]
    
    # Check if the target is a file path
    target_path = Path(target)
    if target_path.is_file():
        try:
            commit_msg = target_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading commit message file: {e}")
            return 1
    else:
        # Otherwise treat as literal commit message text
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
