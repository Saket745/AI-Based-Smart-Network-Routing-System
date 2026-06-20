# Security Governance Matrix: Model Serialization

This matrix identifies security risks associated with model serialization and deserialization within the `nroute` library.

| Component | Risk | Severity | Exploitability | Priority | Remediation |
|-----------|------|----------|----------------|----------|-------------|
| `CongestionPredictor` | Arbitrary Code Execution (ACE) via `joblib`/`pickle` | High | Medium | P2 | Already partially mitigated with `allow_unsafe=False` default. |
| `AnomalyDetector` | **ACE via `torch.load(weights_only=False)`** | **Critical** | High | **P0** | Change to `weights_only=True` and implement `allow_unsafe` pattern. |
| `AnomalyDetector` | ACE via `joblib.load` | **Critical** | High | **P0** | Implement `allow_unsafe` pattern and block by default. |
| `GCNModel` / `GraphSAGEModel` | ACE via `torch.load` | High | Medium | P1 | Explicitly set `weights_only=True`. |
| CLI `train` / `predict` | Loading untrusted models from arbitrary paths | Medium | Low | P2 | Add warnings or restricted search paths for models. |

## Vulnerability Details

### 1. `AnomalyDetector.load` (Critical)
In `src/nroute/ml/anomaly.py`, the `load` method uses:
```python
torch.load(path, map_location=torch.device("cpu"), weights_only=False)
```
and
```python
joblib.load(path)
```
Both of these allow arbitrary code execution when loading a maliciously crafted model file. Unlike `CongestionPredictor`, this class lacks an `allow_unsafe` toggle and defaults to the most insecure state.

### 2. `GCNModel` & `GraphSAGEModel` (High)
These models use `torch.load(path)` in their `load` methods without specifying `weights_only`. In modern PyTorch, the default is moving towards `True`, but for maximum security and compatibility, it must be explicitly set to `True` as these models only need the `state_dict`.

## Remediation Priority Definitions

- **P0**: Immediate fix required. Direct path to ACE.
- **P1**: High priority. Potential ACE depending on environment/version.
- **P2**: Best practice. Defense in depth.
- **P3**: Documentation/Warning improvement.
