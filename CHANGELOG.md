# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
