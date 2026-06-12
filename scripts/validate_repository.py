#!/usr/bin/env python3
"""
Repository governance and file placement validation script.
Checks file paths, extensions, naming conventions, and file size limits.
Can be run manually, as a pre-commit hook, or in CI pipelines.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# Max file size allowed (5MB)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
WARN_DATA_SIZE_BYTES = 100 * 1024  # 100 KB warn limit for datasets in src/tests

# Allowed extensions in each directory category
ALLOWED_EXTENSIONS = {
    "src": {".py", ".pyi", ".yaml", ".yml", ".json", ".csv", ".txt", ".png", ".gitkeep"},
    "tests": {".py", ".yaml", ".yml", ".json", ".csv", ".txt", ".gitkeep"},
    "docs": {".md", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".html", ".css", ".txt"},
    "configs": {".yaml", ".yml", ".toml", ".json", ".ini", ".conf", ".gitkeep"},
    "experiments": {
        ".py",
        ".ipynb",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".png",
        ".txt",
        ".gitkeep",
    },
    "data": {".csv", ".tsv", ".json", ".pkl", ".parquet", ".gitkeep", ""},
    "scripts": {".py", ".sh", ".bat", ".ps1", ".gitkeep"},
    "models": {".pt", ".pth", ".onnx", ".joblib", ".zip", ".gitkeep"},
}

# Regex naming patterns
PYTHON_FILE_PATTERN = re.compile(r"^[a-z0-9_]+\.py$")
TEST_FILE_PATTERN = re.compile(r"^(test_[a-z0-9_]+|conftest|[a-z0-9_]+_test)\.py$")
DOCS_FILE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.\(\)\s]+$")

# Directories to ignore if walking filesystem
IGNORE_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".benchmarks",
    "__pycache__",
    "build",
    "dist",
}


def get_git_tracked_files(repo_root: Path) -> list[Path]:
    """Get all files currently tracked by git in the repository."""
    try:
        result = subprocess.run(
            ["git", "ls-files"], cwd=str(repo_root), capture_output=True, text=True, check=True
        )
        return [repo_root / line for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.SubprocessError, FileNotFoundError):
        # Fallback to walking directory if git is not available
        return walk_repo(repo_root)


def walk_repo(repo_root: Path) -> list[Path]:
    """Fallback walk of the filesystem to find files, ignoring build/cache dirs."""
    tracked_files = []
    for root, dirs, files in os.walk(repo_root):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            tracked_files.append(Path(root) / file)
    return tracked_files


def validate_file(file_path: Path, repo_root: Path) -> list[str]:
    """Validate a single file path against repository policies."""
    errors = []

    # Resolve relative path from repo root
    try:
        rel_path = file_path.relative_to(repo_root)
    except ValueError:
        return [f"File {file_path} is not under repository root {repo_root}"]

    parts = rel_path.parts
    if not parts:
        return []

    # Get root folder category (e.g. 'src', 'tests', 'docs')
    category = parts[0]

    # Check for file size limits
    if file_path.exists():
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            errors.append(
                f"[{rel_path}] Size ({size / (1024*1024):.2f}MB) exceeds the 5MB maximum limit. "
                "Large files should be stored outside the repo or tracked via Git LFS."
            )

    # If it's a top-level file (e.g. pyproject.toml, README.md), standard check passes
    if len(parts) == 1:
        # Top-level is fine for markdown, configuration, scripts, etc.
        return errors

    # Check directory-specific rules
    ext = file_path.suffix.lower()
    filename = file_path.name

    if category not in ALLOWED_EXTENSIONS:
        if category not in IGNORE_DIRS and not category.startswith("."):
            errors.append(
                f"[{rel_path}] File resides in an unrecognized top-level directory '{category}'. "
                "Please organize files within src/, tests/, docs/, configs/, scripts/, experiments/, models/, or data/."
            )
        return errors

    # 1. Allowed file types
    is_gitkeep = filename == ".gitkeep"
    if ext not in ALLOWED_EXTENSIONS[category] and not is_gitkeep:
        errors.append(
            f"[{rel_path}] File extension '{ext}' is not allowed in '{category}/'. "
            f"Allowed extensions: {', '.join(sorted(list(ALLOWED_EXTENSIONS[category])))}"
        )

    # 2. Dataset warning in source code/test directories
    if (
        category in {"src", "tests"}
        and ext in {".csv", ".json"}
        and file_path.exists()
        and file_path.stat().st_size > WARN_DATA_SIZE_BYTES
    ):
        errors.append(
            f"[{rel_path}] Large dataset ({file_path.stat().st_size / 1024:.1f}KB) detected in source/test directory. "
            "Move dataset files to 'data/' or 'datasets/' directory."
        )

    # 3. Naming convention validations
    if category == "src" and ext == ".py" and not PYTHON_FILE_PATTERN.match(filename):
        errors.append(
            f"[{rel_path}] Python file '{filename}' does not follow snake_case naming convention."
        )

    elif category == "tests" and ext == ".py" and not TEST_FILE_PATTERN.match(filename):
        errors.append(
            f"[{rel_path}] Test file '{filename}' must follow snake_case and be prefixed/suffixed with 'test_' or '_test' (e.g., 'test_routing.py')."
        )

    elif category == "docs" and ext == ".md" and not DOCS_FILE_PATTERN.match(filename):
        errors.append(
            f"[{rel_path}] Documentation markdown name '{filename}' has invalid characters."
        )

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent

    # If file arguments are passed (e.g., via pre-commit), use them. Otherwise, scan all files.
    if len(sys.argv) > 1:
        files_to_check = [Path(arg).resolve() for arg in sys.argv[1:] if os.path.isfile(arg)]
    else:
        print("No files specified. Scanning all git-tracked files in repository...")
        files_to_check = get_git_tracked_files(repo_root)

    total_checked = 0
    all_errors = []

    for file_path in files_to_check:
        # Ignore files inside ignored directories
        rel_path = file_path.relative_to(repo_root) if file_path.is_absolute() else file_path
        parts = rel_path.parts
        if parts and (parts[0] in IGNORE_DIRS or parts[0].startswith(".")):
            continue

        if not file_path.exists():
            continue

        total_checked += 1
        errors = validate_file(file_path, repo_root)
        if errors:
            all_errors.extend(errors)

    print(f"Validated {total_checked} files.")

    if all_errors:
        print("\n[REPOSITORY GOVERNANCE FAILURE] Policy violations detected:\n")
        for err in all_errors:
            print(f"  - {err}")
        print(
            "\nPlease fix these issues before committing. Refer to docs/CONTRIBUTING.md for details.\n"
        )
        return 1

    print("[REPOSITORY GOVERNANCE SUCCESS] All files conform to standards.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
