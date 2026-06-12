# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
