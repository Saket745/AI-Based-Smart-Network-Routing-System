<div align="center">

# 🌐 NRoute

### High-Performance Network Digital Twin & Pre-Flight Validation Platform

**`nroute`** — A deterministic, production-grade Python engine and CLI for network digital twin modeling, what-if change-impact simulation, and automated pre-flight safety policy validation.

[![CI](https://github.com/Saket745/AI-Based-Smart-Network-Routing-System/actions/workflows/ci.yml/badge.svg)](https://github.com/Saket745/AI-Based-Smart-Network-Routing-System/actions)
[![Coverage](https://img.shields.io/badge/Coverage-80.67%25-brightgreen.svg)](https://github.com/Saket745/AI-Based-Smart-Network-Routing-System/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

</div>

---

## 🎯 What is NRoute?

Modern network infrastructure changes are high-risk operations where configuration errors can cause catastrophic routing loops, latency spikes, or full outage cascades. **NRoute** provides an analytical, deterministic **Network Digital Twin** that simulates proposed configuration patches before deployment and validates them against declarative safety policies returning **PASS**, **WARN**, or **BLOCK** verdicts.

| Capability | Description |
|---|---|
| 🛡️ **Pre-Flight Validation Engine** | Deterministic change-impact evaluation returning `PASS`, `WARN`, or `BLOCK` with POSIX exit codes (`0`, `1`, `2`) for CI/CD gates. |
| 💥 **Change Blast-Radius Analysis** | Analytical pairwise reachability delta, path divergence ratio, and latency degradation calculation. |
| ⚡ **Deterministic Routing Engines** | High-performance sub-millisecond **Dynamic-Dijkstra** and **ECMP** multipath pathfinding. |
| 🏗️ **Topology & Config Ingestion** | Full OpenConfig configuration normalization, synthetic topologies (Fat-Tree, Scale-Free), and telemetry ingestion (NetFlow, PCAP). |
| 🌐 **Digital Twin REST API** | FastAPI service exposing `/api/twin/validate`, `/api/health`, `/api/topology`, and `/api/rca` for web dashboards and automation. |
| 🔬 **Research Evidence Baseline** | Rigorous empirical benchmarks comparing classical routing against ML/GNN/RL heuristics (preserved as frozen historical research). |

---

## 📦 Installation

```bash
# Base installation (Digital Twin, Pre-Flight Validation, Dijkstra/ECMP Routing, CLI & REST API)
pip install nroute

# Optional capability extras:
pip install "nroute[torch]"   # Historical Deep Learning & GNN research features (PyTorch)
pip install "nroute[rl]"      # Historical Reinforcement Learning environment (Gymnasium + Stable-Baselines3)
pip install "nroute[pcap]"    # Binary PCAP packet capture ingestion (Scapy)
pip install "nroute[all]"     # Complete platform stack

# From source (development with full test suite and strict typing tooling)
git clone https://github.com/Saket745/AI-Based-Smart-Network-Routing-System.git
cd AI-Based-Smart-Network-Routing-System
pip install -e ".[dev]"
```

**Requirements:** Python 3.10+

---

## 🚀 Quick Start

### 1. Pre-Flight Change Validation (CLI)

Validate a proposed OpenConfig or JSON change patch against a declarative safety policy before pushing to production:

```bash
# Validate change against policy (returns 0 on PASS, 1 on BLOCK, 0/2 on WARN)
nroute twin validate \
  --topology network.json \
  --change proposed_change.yaml \
  --policy safety_policy.yaml

# Emit machine-readable JSON report for CI/CD pipelines
nroute twin validate \
  -t network.json \
  -ch proposed_change.yaml \
  -p safety_policy.yaml \
  --json \
  --strict-warnings
```

### 2. Network Pathfinding & Simulation

```bash
# Generate a Fat-Tree data-center topology
nroute topology generate --type fat-tree --k 4 --output network.json

# Compute optimal routes with Dijkstra or ECMP
nroute route compute --topology network.json --algorithm dijkstra --source 0 --destination 15

# Run a discrete-event simulation with link failure injection
nroute simulate run --topology network.json --algorithm dijkstra --duration 100 --fail-link "0,2" --fail-tick 30
```

### 3. Launch Digital Twin REST API

```bash
# Start the FastAPI digital twin server
nroute api start --host 127.0.0.1 --port 8000
```

---

## 💻 Python Library Usage

```python
from nroute import (
    ChangeImpactSimulator,
    ConfigChange,
    DigitalTwinEngine,
    PolicyGateConfig,
    PreFlightValidator,
    Topology,
)

# 1. Ingest baseline network topology
twin = DigitalTwinEngine()
twin.load_topology("network.json")

# 2. Ingest device configuration (optional)
twin.ingest_config("configs/spine01.json")

# 3. Validate a proposed network change patch against safety policy
result = twin.validate_change(
    change="changes/maintenance_drain_link.yaml",
    policy="policies/strict_datacenter.yaml",
)

# 4. Check policy evaluation verdict
print(f"Verdict:  [{result.verdict.value}] - {result.summary}")
print(f"Duration: {result.execution_duration_ms:.2f} ms")
print(f"Newly Unreachable Pairs: {result.blast_radius_summary['newly_unreachable_pairs']}")

if not result.gate_passed:
    for violation in result.blocking_violations:
        print(f"BLOCK: {violation}")
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              CLI & REST API Layer (Click / FastAPI)             │
│        nroute twin validate   │   POST /api/twin/validate       │
├─────────────────────────────────────────────────────────────────┤
│            Pre-Flight Automated Validation Engine               │
│   ┌───────────────────────────┐   ┌─────────────────────────┐   │
│   │   Declarative Policy      │   │  Change-Impact Engine   │   │
│   │   (PASS / WARN / BLOCK)   │   │  (Blast-Radius Calc)    │   │
│   └───────────────────────────┘   └─────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                     Digital Twin Core Engine                    │
│   Dynamic-Dijkstra  │  ECMP Multipath  │  Discrete Simulator    │
├─────────────────────────────────────────────────────────────────┤
│                  Core Graph & Normalization Layer               │
│   OpenConfig Normalizer  │  NetworkX Topology  │  NetFlow/PCAP  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Empirical Performance Baselines

Performance metrics are verified via automated benchmark suites under `tests/benchmarks/`:

| Benchmark Metric | Empirical Measured Performance | Target SLA | Status |
|---|---|---|---|
| **Dijkstra Shortest Path (500 nodes)** | **0.69 ms** (Mean) | $\le 10\text{ ms}$ | **Exceeds target by 14x** |
| **ECMP Multipath Routing (500 nodes)** | **6.08 ms** (Mean) | $\le 20\text{ ms}$ | **Exceeds target by 3.3x** |
| **Simulation Throughput (1000 nodes)** | **513 ticks/sec** ($1.94\text{ ms/tick}$) | $\ge 100\text{ ticks/sec}$ | **Exceeds target by 5x** |
| **Pre-Flight Validation Engine** | **1.4 ms – 12.3 ms** | $\le 50\text{ ms}$ | **Real-time CI/CD Gating** |

---

## 🧪 Quality & Verification

```bash
# Run full test suite (660+ tests)
pytest -v

# Run static linter & formatter
ruff check src/ tests/
ruff format --check src/ tests/

# Run strict static type checking
mypy src/nroute --strict
```

---

## 📄 Documentation

- [Quickstart Guide](docs/quickstart.md)
- [CLI Reference Guide](docs/cli_reference.md)
- [API Reference Guide](docs/api_reference.md)
- [Production Deployment Guidelines](docs/deployment.md)
- [Custom Extensions](docs/custom_extensions.md)
- [Archived Specs & Historical Research](docs/archive/)

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Saket** — [GitHub](https://github.com/Saket745)
