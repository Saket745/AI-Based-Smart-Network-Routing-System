## 2026-09-22 - macOS and Windows Path Symlink Resolution in PyTorch Exception Assertions
**Vulnerability:** Test assertion failure during PyTorch model secure loading exception handling.
**Learning:** PyTorch/OS-level file operations or exception message string formatting may normalize paths via `os.path.realpath` (e.g. resolving macOS `/var` -> `/private/var` symlinks or Windows `RUNNER~1` 8.3 short paths). Comparing raw temporary directory path strings directly in `excinfo` exception assertions fails on cross-platform runners.
**Prevention:** In exception assertions involving file paths, check that the expected string matches either `path` or `os.path.realpath(path)`.
