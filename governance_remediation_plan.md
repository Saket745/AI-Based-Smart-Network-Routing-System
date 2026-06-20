# Governance Remediation Plan

## P0: Immediate Fixes (Today)
1.  **Security**: Refactor `AnomalyDetector` to use secure loading (`weights_only=True` and `allow_unsafe` flag).
2.  **Commit Governance**: Update `validate_commit_msg.py` to support `Revert "..."` and `fixup!` / `wip` patterns for feature branches.
3.  **PR Policy**: Document the "Squash and Merge" requirement in `CONTRIBUTING.md`.

## P1: Short-term Fixes (1 Week)
1.  **CI Optimization**: Add `actions/cache` to `.github/workflows/ci.yml`.
2.  **Branch Validation**: Implement a branch naming validator script and add to CI.
3.  **Security Audit**: Run `pip-audit` and resolve any high-severity CVEs in the dependency tree.

## P2: Medium-term Fixes (1 Month)
1.  **Serialization Migration**: Move all model saving to use native formats (XGBoost JSON) or state_dicts exclusively.
2.  **Architecture**: Implement a `GovernanceManager` within the library to programmatically enforce policies.
3.  **Developer Experience**: Create a CLI command `nroute dev check` to run all governance checks locally.

## P3: Long-term Roadmap
1.  **AI-Agent Integration**: Create a specific governance profile for AI agents (e.g., automated PR descriptions).
2.  **Compliance**: Automate generation of a `GOVERNANCE_COMPLIANCE.md` report on every release.
3.  **Enterprise Readiness**: Integration with OIDC for secure cloud deployments.
