# System Architecture Document

This document details the architectural layout, modules, and component interactions of **nroute** (AI-Based Smart Network Routing System).

---

## 🏗️ High-Level Component Interactions

The system is organized into modular layers with unidirectional dependencies flowing downwards:

```
                  ┌─────────────────────────────┐
                  │      CLI Layer (Click)      │
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │      Public Library API     │
                  └──────────────┬──────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌────────▼────────┐     ┌────────▼────────┐     ┌────────▼────────┐
│  Routing Engine │     │ Data Ingestion  │     │   Simulation    │
│    (Base)       │     │     Engine      │     │     Engine      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │  Core Graph Layer (NetworkX)│
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │      Local Storage / FS     │
                  └─────────────────────────────┘
```

---

## 📁 Repository Directory Structure

```text
AI-Based-Smart-Network-Routing-System/
├── .github/                 # CI workflows (GitHub Actions)
├── configs/                 # Config files for topologies, models, tests
├── data/                    # Datasets (NetFlow CSVs, traffic logs)
├── docs/                    # Architectural plans, specs, templates
│   └── archive/             # Archived historical specs (PRD, TRD)
├── models/                  # Checkpointed ML/RL models and metadata
├── scripts/                 # Utility scripts (traffic generator, baseline trainers)
├── src/
│   └── nroute/
│       ├── api/             # FastAPI REST server & auth middleware
│       ├── audit/           # Audit trail & structured logging
│       ├── cli/             # CLI commands (topology, route, simulate, detect)
│       ├── core/            # Topology, flow/traffic representation, generators
│       ├── ingestion/       # CSV, SNMP, NetFlow/PCAP data parsers
│       ├── ml/              # Congestion predictor, anomaly detector, RL env
│       ├── routing/         # Dijkstra, ECMP, Bellman-Ford, RL router
│       ├── simulation/      # SimulationEngine, FailureInjector, TrafficGenerator
│       └── utils/           # Shared logging, metrics, loaders
└── tests/                   # pytest unit, integration, and benchmark test suites
```

---

## 🧠 Core Modules

### 1. Core Graph Layer (`src/nroute/core/`)
* **`Topology`**: Built on NetworkX, represents nodes (routers, switches, hosts) and directed edges (links) with capacity, latency, status (up/down), packet loss, and utilization attributes with O(1) down-tracking.
* **`FlowRecord`**: Encapsulates packet flow characteristics (source, destination, volume, protocol, timestamps).
* **`TopologyGenerator`**: Generates synthetic topologies (Fat-Tree, Random, Scale-Free, Small-World).

### 2. Routing Engine (`src/nroute/routing/`)
All routers inherit from `BaseRouter`:
* **`DijkstraRouter`**: Finds shortest routes based on link weight/latency attributes.
* **`ECMPRouter`**: Distributes traffic across paths of equal cost to balance utilization.
* **`BellmanFordRouter`**: Distributed distance-vector shortest-path routing.
* **`RLRouter`**: Deep reinforcement learning routing agent using trained policies.
* **`AIRouter`**: High-level AI router unifying anomaly detection, congestion forecasting, and adaptive rerouting.

### 3. Simulation Engine (`src/nroute/simulation/`)
* **`SimulationEngine`**: Runs discrete-event simulation ticks, forwards flows, tracks packet loss, latency, and link saturation.
* **`FailureInjector`**: Schedules link and node failures/recoveries dynamically during simulation runs.
* **`TrafficGenerator`**: Produces configurable traffic matrices (uniform, gravity, hotspot, bimodal).

### 4. Data Ingestion Engine (`src/nroute/ingestion/`)
* Standardizes network telemetry inputs (NetFlow, PCAP, SNMP) into the internal `Topology` and `FlowRecord` formats.

### 5. Machine Learning Layer (`src/nroute/ml/`)
* **`CongestionPredictor`**: XGBoost & LSTM time-series link congestion predictors.
* **`AnomalyDetector`**: Isolation Forest & Autoencoder traffic anomaly detectors.
* **`NetworkRoutingEnv`**: Gymnasium-compatible RL environment for training routing agents.
* **`ModelStore`**: Checkpointed model store with cryptographic SHA-256 integrity verification.

---

## 🎨 Extensibility Guidelines

The system is designed with **Dependency Inversion** at its core.

### Adding a New Routing Algorithm
To add a custom routing algorithm:
1. Inherit from `BaseRouter` in `src/nroute/routing/base.py`.
2. Implement the `compute_path` method.
3. Register using `@register_router("name")` or load via `nroute.yaml` configuration.

Example:
```python
from nroute.core.topology import Topology
from nroute.routing.base import BaseRouter, register_router


@register_router("custom-latency")
class CustomLatencyRouter(BaseRouter):
    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: str | None = "latency",
    ) -> list[str]:
        # Implement custom routing logic
        import networkx as nx

        subgraph = self._get_active_subgraph(topology)
        return list(nx.shortest_path(subgraph, source, destination, weight=weight))
```
