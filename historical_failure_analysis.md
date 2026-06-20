# Historical Failure Analysis

## 1. Failure Categories & Root Causes

Based on the repository history and current state, failures are clustered into the following categories:

### A. Commit Governance (Recurring)
- **Root Cause**: Strict enforcement of Conventional Commits on every intermediate commit.
- **Pattern**: Developers/Agents make "Merge branch" or "fixup" commits that aren't recognized by the regex.
- **Impact**: Blocked PRs despite correct final code.

### B. CI Environment / Dependencies (Frequent)
- **Root Cause**: Missing system-level dependencies (e.g., `libomp` for XGBoost on macOS).
- **Pattern**: Test failures specifically on macOS or Windows runners while passing on Linux.
- **Impact**: Flaky CI results and delayed merging.

### C. Type Safety (Mypy)
- **Root Cause**: Strict MyPy settings without proper third-party type stubs.
- **Pattern**: "Ignore missing imports" being added incrementally as new libraries (torch, xgboost) are introduced.
- **Impact**: Build breaks when new dependencies are added without updating `pyproject.toml`.

### D. Security (Hidden Debt)
- **Root Cause**: Reliance on `joblib` and `pickle` for ML model storage.
- **Pattern**: Incremental adoption of insecure loading patterns in `AnomalyDetector` and `CongestionPredictor`.
- **Impact**: Potential for RCE if untrusted models are loaded.

## 2. Cluster Analysis Matrix

| Cluster | Frequency | Severity | Effort to Fix |
|---------|-----------|----------|---------------|
| Commit Linting | High | Low | Low |
| macOS/System Deps| Medium | Medium | Medium |
| MyPy Strictness | Medium | Low | Low |
| Deserialization | Low | Critical | Medium |

## 3. Remediation Strategy for Technical Debt

1.  **Governance Modernization**: Shift to PR-title validation to reduce the "High Frequency" of commit linting failures.
2.  **Containerized Testing**: Move towards Docker-based CI to eliminate "System Dependency" issues.
3.  **Secure by Default**: Refactor all ML loading code to use `weights_only=True` or JSON-based formats.
