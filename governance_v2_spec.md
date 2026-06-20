# Governance V2 Specification

## 1. Vision
Enterprise-grade, AI-agent compatible governance that prioritizes **security**, **clean history**, and **developer velocity**.

## 2. Commit Policy 2.0
- **Main Branch Integration**: Strictly via **Squash and Merge**.
- **Validation Target**: Only the **PR Title** and **Merge Commits** to `main` must strictly adhere to Conventional Commits.
- **Intermediate Commits**: Validated with a "Warning-only" or "Relaxed" policy (allowing `wip`, `temp`, `fixup!`).
- **Tooling**: Upgrade `scripts/validate_commit_msg.py` to handle `Revert` and `Merge` patterns correctly.

## 3. Branch Policy 2.0
- **Strict Prefixes**: `feat/`, `fix/`, `docs/`, `perf/`, `refactor/`, `ci/`, `security/`, `agent/`.
- **Validation**: CI will reject any PR whose source branch does not follow the naming convention.

## 4. Security Policy 2.0 (Secure-by-Default)
- **Model Loading**: `weights_only=True` is mandatory for all `torch.load` calls.
- **Serialization**: Transition away from `joblib`/`pickle` towards `JSON` (for XGBoost) and `Safetensors` or `state_dict` (for PyTorch).
- **Blocking**: Deserialization of arbitrary Python objects is blocked by default and requires explicit `allow_unsafe=True`.

## 5. CI/CD Architecture 2.0
- **Fast Feedback**: Parallelize Linting and Unit Tests.
- **Caching**: Enable global pip and MyPy caching.
- **Environment**: Standardize runners or use pre-configured containers for ML dependencies (XGBoost/LightGBM).
