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
├── experiments/             # Research sandboxes, notebooks, prototypes
├── models/                  # Saved ML/RL models (joblibs, weights)
├── scripts/                 # Utility and repository validation scripts
├── src/
│   └── nroute/
│       ├── cli/             # CLI command definitions
│       ├── core/            # Topology, traffic representation, generators
│       ├── ingestion/       # CSV, SNMP, PCAP data parsers
│       ├── routing/         # Dijkstra, ECMP, RL routers
│       └── utils/           # Shared utility tools
└── tests/                   # pytest unit/integration test suite
```

---

## 🧠 Core Modules

### 1. Core Graph Layer (`src/nroute/core/`)
* **`Topology`**: Built on NetworkX, represents nodes (routers) and directed edges (links) with capacity, latency, status (up/down), and current load attributes.
* **`TrafficMatrix`**: Dictates the communication requirements (source, destination, volume) between nodes for discrete time steps.
* **`Generators`**: Produces synthetic topologies (Grid, Fat-Tree, Erdős-Rényi) and synthetic traffic distribution profiles.

### 2. Routing Engine (`src/nroute/routing/`)
All routers inherit from [BaseRouter](file:///c:/Users/mssak/OneDrive/Desktop/Network%20Route%20Optimizer/AI-Based-Smart-Network-Routing-System/src/nroute/routing/base.py):
* **`DijkstraRouter`**: Finds shortest routes based on link weight/latency attributes.
* **`ECMPRouter`**: Distributes traffic across paths of equal cost to balance utilization.
* **`FallbackRouter`**: Chains multiple routers (e.g., trying an AI-based router first, falling back to Dijkstra if it fails).

### 3. Simulation Engine (`src/nroute/core/`)
* **`Simulator`**: Runs discrete-event loops. Applies a routing strategy to a given topology and traffic matrix over time, injecting link failures or traffic spikes to calculate packet loss, throughput, and link utilization.

### 4. Data Ingestion Engine (`src/nroute/ingestion/`)
* Standardizes network metadata inputs (NetFlow, PCAP, SNMP) into the internal `Topology` and `TrafficMatrix` representations.

---

## 🎨 Extensibility Guidelines

The system is designed with **Dependency Inversion** at its core.

### Adding a New Routing Algorithm
To add a custom routing algorithm (e.g., an ML-based path selector):
1. Inherit from `BaseRouter` in `src/nroute/routing/base.py`.
2. Implement the `compute_path` method.
3. Hook the new router into the CLI options.

Example template:
```python
from nroute.routing.base import BaseRouter
from nroute.core.topology import Topology

class MLPredictiveRouter(BaseRouter):
    def __init__(self, model_path: str):
        # Load your model weights
        pass

    def compute_path(self, topology: Topology, source: str, destination: str, weight=None) -> list[str]:
        # Implement path choice using graph attributes + model predictions
        pass
```

### ML/RL Model Integration Boundaries
* **State Space:** Provided by the active sub-graph view in `BaseRouter._get_active_subgraph(topology)`.
* **Action Space:** Paths selected or link metrics/weights assigned.
* **Model Serialization:** Serialized models reside in `models/` (excluded from git if large via `.gitignore`) and configuration parameters reside in `configs/`.
