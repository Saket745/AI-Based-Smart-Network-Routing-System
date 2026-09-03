# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.3.0] - 2026-09-03

### Added
- **Pre-Flight Change-Impact Validation Engine (`nroute twin validate`):**
  - Deterministic evaluation of proposed network change patches against declarative safety policies.
  - Declarative policy gate thresholds for latency increase (`max_latency_increase_ms`), path churn ratio (`max_path_changed_ratio`), newly severed reachability (`allow_newly_unreachable_pairs`), and critical node connectivity (`protected_nodes`).
  - Strict CI/CD POSIX exit code contracts: `0` for PASS, `1` for BLOCK, `2` for WARN under `--strict-warnings`, and standard error codes `64` (CLI parameter error), `65` (data format error), and `70` (execution error).
  - Machine-readable JSON output schema (`--json`) containing evaluation provenance (Git commit SHA, topology hash, patch hash, policy hash) and blast-radius summaries.
- **REST Validation Endpoint (`POST /api/twin/validate`):**
  - Integrated FastAPI endpoint mirroring the CLI validation engine with full schema parity and constant-time Bearer token authentication.
- **Digital Twin Engine Public Library Exports:**
  - Exposed `DigitalTwinEngine`, `PreFlightValidator`, `PolicyGateConfig`, `ValidationResult`, `ValidationVerdict`, `ChangeImpactSimulator`, and `ConfigChange` in the public `nroute` top-level namespace.
- **Local Developer Authentication Discovery:**
  - Added automatic console display of the generated session token on `nroute api start` when `NROUTE_API_TOKEN` is unset, preventing 401 local lockout without weakening production security.
- **Windows Console Unicode Fallback:**
  - Portable ASCII fallback (`[UP]`, `[DOWN]`) for `nroute topology show` under Windows consoles with non-UTF-8 character maps (`cp1252`), preventing `UnicodeEncodeError`.

### Changed
- **Strategic Product Repositioning:**
  - Refocused documentation, CLI descriptions, and package metadata on the "High-Performance Network Digital Twin & Pre-Flight Change-Impact Validation Platform".
  - Demoted historical AI/RL/GNN exploration to frozen empirical research baselines preserved under milestone tags `v1.0.0-research-phase1` and `v1.1.0-research-phase2`.
  - Replaced non-existent `results.plot_throughput()` in README quickstart with verified Digital Twin validation workflows.
- **Container Build Hardening:**
  - Cleaned up `Dockerfile` multi-stage build, deduplicating corrupted build layers and ensuring unprivileged non-root execution (`useradd -u 10001 nroute`).
  - Corrected `nroute train` subcommand invocation in `docker-compose.yml`.

### Fixed
- **Strict Static Typing:**
  - Fixed mypy return-type violation in `src/nroute/ml/rl_env.py` to achieve 100% clean `mypy src/nroute --strict`.
- **Git Branch Consolidation:**
  - Consolidated 318 legacy remote branches down to a single authoritative `main` trunk while preserving all 4 milestone tags intact.

## [0.2.0] - 2026-06-21

### Added
- **Enterprise-ready CLI & Exporters:** Added CSV, JSON, and GraphML exporter modules (`exporters.py`) with support for importing/exporting simulation outputs and network topology metrics.
- **Baseline Machine Learning Models:** Created baseline training script (`train_baseline_models.py`) training scikit-learn Isolation Forest (anomaly detection), XGBoost (congestion prediction), and Stable-Baselines3 PPO (RL-based routing agent) models under 5MB size limits.
- **Docker & Kubernetes Production Hardening:** Hardened Dockerfile with pegged Python image, non-root `nroute` user, and OCI labels. Developed Kubernetes deployment templates containing namespaces and Persistent Volume Claims (PVC).
- **Security & Supply Chain Security:** Configured Trivy container image scanning and Anchore Syft Software Bill of Materials (SBOM) generation into GitHub Actions.
- **PyPI Release Automation:** Configured Github Actions publishing workflow using secure OIDC Trusted Publisher authentication.
- **Comprehensive Benchmarks & Integration Tests:** Developed automated Dijkstra/RL routing and simulation engine performance benchmarks. Created End-to-End integration tests for PCAP/NetFlow ingestion and full network route optimization loops.

## [0.1.0] - 2026-06-11

### Added
- **Core Scaffolding:** Initial repository setup with configuration directories, documentation, testing, and linting rules.
- **Topology Engine:** Support for creating fat-tree, grid, and random topologies using NetworkX.
- **Routing Module:** Dijkstra and ECMP (Equal-Cost Multi-Path) routing implementation with standard route validation checks.
- **Simulation Engine:** Discrete-event traffic simulation with dynamic flow paths, congestion metrics, and delay measurements.
- **CLI Tool:** Initial CLI interface (`nroute`) supporting topology generation, route computation, and simulations comparison.
- **CI/CD Pipeline:** GitHub Actions configuration running Ruff, MyPy, and PyTest across multiple Operating Systems and Python versions.

### Fixed
- Diverged git history resolved by synchronizing the local project codebase with the remote GitHub main repository.
