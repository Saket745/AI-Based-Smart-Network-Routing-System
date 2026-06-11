<div align="center">

# 🌐 AI-Based Smart Network Routing System

**`nroute`** — A production-grade Python CLI and library for simulating, visualizing, and optimizing network routing using AI/ML.

[![CI](https://github.com/Saket745/AI-Based-Smart-Network-Routing-System/actions/workflows/ci.yml/badge.svg)](https://github.com/Saket745/AI-Based-Smart-Network-Routing-System/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

</div>

---

## 🚧 Status: Under Active Development

This project is currently in **Phase 1** (Project Scaffold). Core features are being built phase by phase. See the [Implementation Plan](docs/Implementation_Plan.md) for details.

---

## 🎯 What is nroute?

Traditional routing algorithms (Dijkstra, OSPF, BGP) are **reactive** — they can't predict congestion, detect anomalies, or learn from traffic patterns. **nroute** bridges this gap with AI:

| Feature | Description |
|---------|-------------|
| 🔮 **Congestion Prediction** | XGBoost/LSTM models predict link congestion 5-15 minutes ahead |
| 🛡️ **Anomaly Detection** | Isolation Forest detects DDoS, link failures, and traffic black holes |
| 🧠 **RL-Based Routing** | PPO/DQN agents learn optimal routing policies beyond shortest-path |
| 🔄 **Adaptive Rerouting** | Automatic path recalculation when congestion or anomalies are detected |
| 🏗️ **Topology Engine** | Generate synthetic networks or import real-world data (NetFlow, pcap, SNMP) |
| ⚡ **Simulation Engine** | Discrete-event simulation with traffic generation and failure injection |

---

## 📦 Installation

```bash
# From source (development)
git clone https://github.com/Saket745/AI-Based-Smart-Network-Routing-System.git
cd AI-Based-Smart-Network-Routing-System
pip install -e ".[dev]"

# From PyPI (coming soon)
# pip install nroute
```

**Requirements:** Python 3.10+

---

## 🚀 Quick Start

### CLI Usage

```bash
# Generate a network topology
nroute topology generate --type fat-tree --k 4 --output network.json

# Compute routes
nroute route compute --topology network.json --algorithm dijkstra --source 0 --destination 15

# Run a simulation
nroute simulate run --topology network.json --algorithm dijkstra --duration 100

# Compare algorithms
nroute simulate compare --topology network.json --algorithms dijkstra,rl --duration 100
```

### Library Usage

```python
from nroute import Topology, Simulator, AIRouter

# Generate a topology
topo = Topology.generate("fat-tree", k=4)

# Classical routing
paths = topo.compute_routes(algorithm="dijkstra", source="A", destination="Z")

# AI-powered routing
router = AIRouter(model="rl-ppo", topology=topo)
router.train(traffic_data="data/traffic.csv", epochs=100)
ai_paths = router.compute_routes(source="A", destination="Z")

# Run simulation
sim = Simulator(topology=topo, algorithm=router, duration=3600)
results = sim.run()
results.plot_throughput()
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Layer (Click)                        │
├─────────────────────────────────────────────────────────────────┤
│                      Public Library API                         │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│  Routing     │  ML/AI       │  Simulation  │  Data Ingestion    │
│  Engine      │  Engine      │  Engine      │  Engine            │
├──────────────┴──────────────┴──────────────┴────────────────────┤
│                    Core Graph Layer (NetworkX)                   │
├─────────────────────────────────────────────────────────────────┤
│                   Data & Model Storage (Local FS)               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧪 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linter
ruff check src/ tests/

# Run type checker
mypy src/nroute --strict

# Run all checks
pre-commit run --all-files
```

---

## 📄 Documentation

- [Product Requirements Document (PRD)](docs/PRD.md)
- [Technical Requirements Document (TRD)](docs/TRD.md)
- [Implementation Plan](docs/Implementation_Plan.md)
- [API Reference](docs/api_reference.md) *(coming soon)*

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Saket** — [GitHub](https://github.com/Saket745)
