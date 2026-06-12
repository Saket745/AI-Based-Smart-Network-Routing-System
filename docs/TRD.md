# Technical Requirements Document (TRD)
# AI-Based Smart Network Routing System

**Version:** 1.0
**Date:** June 10, 2026
**Author:** Saket
**Repository:** https://github.com/Saket745/AI-Based-Smart-Network-Routing-System
**Companion:** [PRD.md](file:///c:/Users/mssak/OneDrive/Desktop/Network%20Route%20Optimizer/PRD.md)

---

## 1. Architecture Overview

The system follows a **layered library architecture** — each layer is independently testable, with clean interfaces between them. There is no web server, database server, or external service dependency. Everything runs as a single-process Python application invoked via CLI or imported as a library.

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Layer (Click)                        │
│   nroute topology | route | simulate | train | predict | export │
├─────────────────────────────────────────────────────────────────┤
│                      Public Library API                         │
│   Topology | Simulator | AIRouter | Predictor | Detector        │
├──────────────┬──────────────┬──────────────┬────────────────────┤
│  Routing     │  ML/AI       │  Simulation  │  Data Ingestion    │
│  Engine      │  Engine      │  Engine      │  Engine            │
├──────────────┴──────────────┴──────────────┴────────────────────┤
│                    Core Graph Layer (NetworkX)                   │
├─────────────────────────────────────────────────────────────────┤
│                   Data & Model Storage (Local FS)               │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Descriptions

| Layer                | Responsibility                                                                               |
| -------------------- | -------------------------------------------------------------------------------------------- |
| **CLI Layer**        | Parses user commands, validates arguments, delegates to the Library API, and formats output.  |
| **Public Library API** | The stable, documented Python interface developers import. Wraps internal engines.          |
| **Routing Engine**   | Classical algorithm implementations (Dijkstra, Bellman-Ford, ECMP) and the RL routing agent. |
| **ML/AI Engine**     | Model training, inference, and management for congestion prediction and anomaly detection.   |
| **Simulation Engine** | Discrete-event simulation loop, traffic generation, failure injection, and metrics collection.|
| **Data Ingestion Engine** | Parsers for NetFlow, SNMP exports, pcap, CSV, and JSON. Normalizes data into internal graph format. |
| **Core Graph Layer** | Underlying graph data structure (NetworkX DiGraph) with edge/node attribute management.      |
| **Data & Model Storage** | Local filesystem for saving/loading topologies, trained models, simulation results.       |

---

## 2. Technology Stack

### 2.1 Language & Runtime

| Component          | Choice                      | Rationale                                                                              |
| ------------------ | --------------------------- | -------------------------------------------------------------------------------------- |
| **Language**       | Python 3.10+                | Richest ML/networking ecosystem; NumPy, PyTorch, NetworkX all native. User-suggested openness maps best to Python. |
| **Runtime**        | CPython                     | Standard; broadest library compatibility.                                              |
| **Package Manager** | pip + pyproject.toml       | Modern Python packaging standard. `setuptools` backend with `pyproject.toml`.          |
| **Virtual Env**    | venv / uv                   | Lightweight isolation. `uv` for faster installs during development.                    |

### 2.2 Core Libraries

| Domain                     | Library                    | Version   | Purpose                                                                |
| -------------------------- | -------------------------- | --------- | ---------------------------------------------------------------------- |
| **Graph / Topology**       | `networkx`                 | ≥3.2      | Graph creation, manipulation, classical shortest-path algorithms.      |
| **Numerical Computing**    | `numpy`                    | ≥1.26     | Array operations, matrix computations, traffic matrices.               |
| **Data Processing**        | `pandas`                   | ≥2.1      | Tabular data manipulation for traffic logs, metrics, and results.      |
| **CLI Framework**          | `click`                    | ≥8.1      | Robust CLI with subcommands, argument validation, help generation.     |
| **Terminal UI**            | `rich`                     | ≥13.0     | Pretty tables, progress bars, colored output, ASCII topology display.  |
| **Configuration**          | `pydantic`                 | ≥2.5      | Typed configuration models, validation, serialization.                 |
| **Logging**                | `structlog`                | ≥24.1     | Structured, JSON-capable logging for production use.                   |

### 2.3 ML/AI Libraries

| Domain                     | Library                    | Version   | Purpose                                                                |
| -------------------------- | -------------------------- | --------- | ---------------------------------------------------------------------- |
| **Deep Learning**          | `torch` (PyTorch)          | ≥2.2      | RL agent (DQN/PPO), LSTM for congestion prediction, autoencoders.      |
| **Reinforcement Learning** | `stable-baselines3`        | ≥2.2      | Pre-built PPO/DQN implementations with Gymnasium interface.            |
| **RL Environment**         | `gymnasium`                | ≥0.29     | Standard RL environment interface for the routing environment.         |
| **Classical ML**           | `scikit-learn`             | ≥1.4      | Isolation Forest (anomaly detection), XGBoost alternative, preprocessing. |
| **Gradient Boosting**      | `xgboost`                  | ≥2.0      | Alternative congestion predictor; often faster/better than LSTM for tabular data. |
| **Model Serialization**    | `torch` (native) + `joblib` | —        | Save/load PyTorch models and scikit-learn pipelines.                   |

### 2.4 Data Ingestion Libraries

| Format               | Library                     | Purpose                                                       |
| --------------------- | --------------------------- | ------------------------------------------------------------- |
| **NetFlow v5/v9**     | Custom parser + `struct`    | Parse binary NetFlow records into flow DataFrames.             |
| **IPFIX**             | Custom parser               | Extension of NetFlow v9 parsing.                               |
| **pcap**              | `scapy`                     | Extract flow-level summaries (src/dst IP, ports, byte counts). |
| **SNMP MIB-II**       | `pysnmp` (parse only)       | Parse exported SNMP interface counter data (CSV/JSON dumps).   |
| **CSV / JSON**        | `pandas` + `json`           | Generic edge-list and node-attribute import.                   |

### 2.5 Visualization Libraries

| Library              | Purpose                                                                |
| -------------------- | ---------------------------------------------------------------------- |
| `matplotlib`         | Publication-quality plots (latency curves, utilization heatmaps).      |
| `plotext`            | Terminal-based inline charts (for CLI mode without GUI).               |
| `rich`               | ASCII tables, tree diagrams, topology summaries in terminal.           |

### 2.6 Testing & Quality

| Tool                 | Purpose                                                                |
| -------------------- | ---------------------------------------------------------------------- |
| `pytest`             | Unit and integration testing framework.                                |
| `pytest-cov`         | Code coverage measurement (target: ≥80%).                             |
| `pytest-benchmark`   | Performance benchmarking for routing computations.                     |
| `mypy`               | Static type checking (strict mode).                                    |
| `ruff`               | Linting and formatting (replaces flake8 + black + isort).             |
| `pre-commit`         | Git hooks for enforcing linting, type checks, and tests before commit. |

### 2.7 CI/CD & Deployment

| Tool                 | Purpose                                                                |
| -------------------- | ---------------------------------------------------------------------- |
| `GitHub Actions`     | CI pipeline: lint → type-check → test → coverage → build.             |
| `pyproject.toml`     | Single source of truth for project metadata, dependencies, and build.  |
| `setuptools`         | Build backend for pip-installable wheel/sdist.                         |
| `PyPI`               | Distribution target (future: `pip install nroute`).                    |

---

## 3. Project Structure

```
AI-Based-Smart-Network-Routing-System/
├── pyproject.toml                  # Project config, dependencies, entry points
├── README.md                       # Quickstart, examples, badges
├── LICENSE                         # MIT or Apache 2.0
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI pipeline
├── docs/
│   ├── PRD.md                      # Product Requirements Document
│   ├── TRD.md                      # This document
│   └── api_reference.md            # Auto-generated API docs
├── src/
│   └── nroute/                     # Main package
│       ├── __init__.py             # Public API exports
│       ├── __main__.py             # `python -m nroute` entry point
│       ├── cli/                    # CLI layer
│       │   ├── __init__.py
│       │   ├── main.py             # Root Click group
│       │   ├── topology_cmd.py     # `nroute topology` subcommands
│       │   ├── route_cmd.py        # `nroute route` subcommands
│       │   ├── simulate_cmd.py     # `nroute simulate` subcommands
│       │   ├── train_cmd.py        # `nroute train` command
│       │   ├── predict_cmd.py      # `nroute predict` command
│       │   ├── detect_cmd.py       # `nroute detect` command
│       │   └── export_cmd.py       # `nroute export` command
│       ├── core/                   # Core data structures
│       │   ├── __init__.py
│       │   ├── topology.py         # Topology class (wraps NetworkX DiGraph)
│       │   ├── traffic.py          # TrafficMatrix, FlowRecord models
│       │   ├── metrics.py          # SimulationMetrics, RouteMetrics
│       │   └── config.py           # Pydantic configuration models
│       ├── routing/                # Routing algorithms
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract Router interface
│       │   ├── dijkstra.py         # Dijkstra implementation
│       │   ├── bellman_ford.py     # Bellman-Ford implementation
│       │   ├── ecmp.py             # Equal-Cost Multi-Path
│       │   └── rl_router.py        # RL-based AI router (PPO/DQN)
│       ├── ml/                     # ML/AI models
│       │   ├── __init__.py
│       │   ├── congestion.py       # Congestion prediction (LSTM / XGBoost)
│       │   ├── anomaly.py          # Anomaly detection (Isolation Forest / Autoencoder)
│       │   ├── rl_env.py           # Gymnasium environment for RL training
│       │   ├── feature_eng.py      # Feature engineering for traffic data
│       │   └── model_store.py      # Save/load/version trained models
│       ├── simulation/             # Simulation engine
│       │   ├── __init__.py
│       │   ├── engine.py           # Main simulation loop
│       │   ├── traffic_gen.py      # Traffic pattern generators
│       │   ├── failure_injector.py # Link/node failure injection
│       │   └── collector.py        # Metrics collection during simulation
│       ├── ingestion/              # Data ingestion
│       │   ├── __init__.py
│       │   ├── netflow.py          # NetFlow v5/v9 parser
│       │   ├── pcap.py             # pcap flow extractor
│       │   ├── snmp.py             # SNMP export parser
│       │   ├── csv_json.py         # Generic CSV/JSON importer
│       │   └── normalizer.py       # Normalize all formats to internal representation
│       ├── visualization/          # Output & visualization
│       │   ├── __init__.py
│       │   ├── plots.py            # Matplotlib plot generators
│       │   ├── terminal.py         # Rich/plotext terminal visualizations
│       │   └── exporters.py        # JSON/CSV export utilities
│       └── utils/                  # Shared utilities
│           ├── __init__.py
│           ├── logging.py          # Structlog configuration
│           ├── random.py           # Seeded random number management
│           └── validators.py       # Input validation helpers
├── models/                         # Pre-trained model weights (bundled)
│   ├── congestion_xgb_v1.joblib
│   ├── anomaly_iforest_v1.joblib
│   └── rl_ppo_v1.zip
├── data/                           # Sample data for demos & tests
│   ├── sample_topology.json
│   ├── sample_netflow.csv
│   └── sample_traffic.csv
├── tests/                          # Test suite
│   ├── conftest.py                 # Shared fixtures
│   ├── unit/
│   │   ├── test_topology.py
│   │   ├── test_dijkstra.py
│   │   ├── test_bellman_ford.py
│   │   ├── test_ecmp.py
│   │   ├── test_rl_router.py
│   │   ├── test_congestion.py
│   │   ├── test_anomaly.py
│   │   ├── test_simulation.py
│   │   ├── test_traffic_gen.py
│   │   └── test_ingestion.py
│   ├── integration/
│   │   ├── test_cli.py
│   │   ├── test_full_pipeline.py
│   │   └── test_real_data.py
│   └── benchmarks/
│       ├── bench_routing.py
│       └── bench_simulation.py
└── scripts/                        # Development utilities
    ├── generate_sample_data.py
    └── train_baseline_models.py
```

---

## 4. Detailed Technical Decisions

### 4.1 Graph Representation

**Decision:** Use `networkx.DiGraph` as the underlying topology structure.

**Rationale:**
- NetworkX is the de facto standard for graph operations in Python.
- Built-in implementations of Dijkstra, Bellman-Ford, and many graph algorithms.
- Rich attribute system for edges (bandwidth, latency, utilization) and nodes (type, capacity).
- Sufficient performance for ≤5,000 edges. For larger graphs (future), can swap to `graph-tool` or `igraph`.

**Edge Attribute Schema:**
```python
{
    "bandwidth": float,       # Mbps — total link capacity
    "latency": float,         # ms — base propagation delay
    "jitter": float,          # ms — latency variance
    "packet_loss": float,     # 0.0-1.0 — base packet loss rate
    "utilization": float,     # 0.0-1.0 — current traffic load
    "weight": float,          # Computed routing weight (derived metric)
    "status": str,            # "up" | "down" | "degraded"
}
```

**Node Attribute Schema:**
```python
{
    "type": str,              # "router" | "switch" | "host" | "gateway"
    "capacity": float,        # Max throughput in Mbps
    "status": str,            # "up" | "down"
    "location": Optional[str] # Logical grouping / area
}
```

### 4.2 Reinforcement Learning Environment

**Decision:** Custom `gymnasium.Env` for routing.

**State Space:**
- Node-level features: utilization, queue depth, processing delay.
- Edge-level features: bandwidth, latency, current utilization, packet loss.
- Global features: total throughput, average latency, active flows count.
- Represented as a flattened feature vector or adjacency matrix with features.

**Action Space:**
- Discrete: Select next-hop node from neighbors of current node.
- Action masking applied to prevent invalid hops (down links, already-visited nodes).

**Reward Function:**
```
reward = α × (1 / latency) + β × throughput - γ × packet_loss - δ × path_length
```
Where α, β, γ, δ are configurable hyperparameters.

**Training:**
- Algorithm: PPO (via `stable-baselines3`) — stable, parallelizable, good for discrete actions.
- Fallback: DQN for simpler topologies / faster convergence.
- Training runs inside the simulation engine: agent routes packets, environment provides rewards.

### 4.3 Congestion Prediction Model

**Decision:** Dual-model approach — XGBoost (primary) + LSTM (optional).

**Input Features (per link, per time step):**
| Feature                    | Description                        |
| -------------------------- | ---------------------------------- |
| `utilization_t`            | Current utilization                |
| `utilization_t-1..t-n`    | Historical utilization (window=12) |
| `bandwidth`                | Link capacity                      |
| `avg_latency_t`           | Current average latency            |
| `flow_count_t`            | Number of active flows             |
| `hour_of_day`             | Temporal feature                   |
| `day_of_week`             | Temporal feature                   |
| `neighbor_utilization_avg` | Average utilization of adjacent links |

**Output:** Binary classification (congested / not congested in next N minutes) + probability score.

**Why XGBoost Primary:**
- Faster training and inference than LSTM.
- Better performance on tabular/structured features.
- No GPU requirement.
- LSTM available as optional model for users who want sequence modeling.

### 4.4 Anomaly Detection Model

**Decision:** Isolation Forest (primary) + Autoencoder (optional).

**Input Features:**
| Feature                    | Description                         |
| -------------------------- | ----------------------------------- |
| `bytes_per_second`         | Traffic volume                      |
| `packets_per_second`       | Packet rate                         |
| `flow_count`               | Active flows                        |
| `avg_packet_size`          | Mean packet size                    |
| `src_ip_entropy`           | Diversity of source IPs             |
| `dst_port_entropy`         | Diversity of destination ports      |
| `utilization_delta`        | Rate of change in utilization       |
| `latency_spike_flag`       | Binary: sudden latency increase     |

**Output:** Anomaly score (0.0-1.0) + anomaly label (normal / anomalous) + anomaly type suggestion (DDoS, link failure, black hole).

**Why Isolation Forest Primary:**
- Unsupervised — no labeled anomaly data needed.
- Fast inference (sub-millisecond per sample).
- Low memory footprint.
- Autoencoder available for users who want deep-learning-based detection.

### 4.5 Simulation Engine

**Decision:** Discrete-event simulation with configurable tick rate.

**Architecture:**
```
SimulationEngine
├── Clock (tick counter / event queue)
├── TrafficGenerator (creates flow requests per tick)
├── Router (selected algorithm computes paths)
├── ForwardingEngine (moves packets along paths, applies latency/loss)
├── FailureInjector (triggers failures at scheduled ticks)
├── MetricsCollector (records per-tick metrics)
└── ResultsAggregator (post-simulation analysis)
```

**Simulation Loop (per tick):**
1. Generate new traffic flows (from `TrafficGenerator`).
2. Check for scheduled failures (from `FailureInjector`).
3. Update topology state (link utilizations, statuses).
4. Route new flows (via selected `Router`).
5. Forward existing flows (apply latency, decrement TTL, apply packet loss).
6. Collect metrics (throughput, latency, loss, utilization per link).
7. Advance clock.

**Reproducibility:** All random operations use a seed from `nroute.utils.random`. Seed is configurable via CLI (`--seed`) and API (`seed=` parameter).

### 4.6 Data Ingestion Pipeline

**Decision:** Adapter pattern with a common `normalizer`.

```
Raw Data (NetFlow/pcap/SNMP/CSV/JSON)
    │
    ▼
Format-Specific Parser (netflow.py / pcap.py / etc.)
    │
    ▼
Normalizer (normalizer.py)
    │   - Standardizes column names
    │   - Validates data types
    │   - Resolves IP addresses to node IDs
    │   - Computes derived metrics (utilization from byte counts + bandwidth)
    │
    ▼
Internal Representation (Topology + TrafficMatrix)
```

**Supported Input Formats:**

| Format          | File Extension(s) | Key Fields Extracted                              |
| --------------- | ------------------ | ------------------------------------------------- |
| **NetFlow v5**  | `.nf`, `.flow`     | src_ip, dst_ip, bytes, packets, duration, protocol |
| **NetFlow v9**  | `.nf9`             | Same as v5 + templates                            |
| **pcap**        | `.pcap`, `.pcapng` | Flow 5-tuple, byte/packet counts, timestamps      |
| **SNMP export** | `.csv`, `.json`    | interface_id, in_octets, out_octets, speed, status |
| **CSV edge list** | `.csv`           | src, dst, bandwidth, latency, + optional columns  |
| **JSON topology** | `.json`          | nodes[], edges[] with arbitrary attributes         |

---

## 5. Configuration Management

### 5.1 Configuration File

**Location:** `~/.nroute/config.yaml` (user-level) or `./nroute.yaml` (project-level, takes precedence).

**Schema (Pydantic model):**

```yaml
# nroute.yaml — Example configuration
general:
  log_level: INFO           # DEBUG | INFO | WARNING | ERROR
  log_format: json          # json | text
  seed: 42                  # Global random seed (null = random)
  output_dir: ./output      # Default output directory

topology:
  default_type: random      # random | fat-tree | scale-free | small-world
  default_nodes: 50
  default_edge_probability: 0.1
  default_bandwidth: 1000   # Mbps
  default_latency: 5        # ms

simulation:
  tick_duration: 1.0        # Seconds per tick (simulation time)
  max_ticks: 3600           # Default simulation duration
  traffic_model: gravity    # uniform | gravity | hotspot | bursty

ml:
  congestion_model: xgboost       # xgboost | lstm
  anomaly_model: isolation_forest  # isolation_forest | autoencoder
  rl_algorithm: ppo                # ppo | dqn
  prediction_horizon: 10          # Minutes ahead
  training_epochs: 100
  batch_size: 64
  learning_rate: 0.001

routing:
  default_algorithm: dijkstra     # dijkstra | bellman-ford | ecmp | rl
  weight_metric: latency          # latency | utilization | composite
  k_shortest_paths: 3             # For ECMP and rerouting alternatives

export:
  format: json                    # json | csv
  include_plots: true
  plot_format: png                # png | svg | pdf
  plot_dpi: 150
```

### 5.2 Configuration Precedence

```
CLI arguments  >  Environment variables (NROUTE_*)  >  ./nroute.yaml  >  ~/.nroute/config.yaml  >  Defaults
```

---

## 6. Error Handling Strategy

### 6.1 Exception Hierarchy

```python
class NRouteError(Exception):
    """Base exception for all nroute errors."""

class TopologyError(NRouteError):
    """Invalid topology operations."""

class IngestionError(NRouteError):
    """Data import/parsing failures."""

class RoutingError(NRouteError):
    """No valid route found, algorithm failure."""

class SimulationError(NRouteError):
    """Simulation engine errors."""

class ModelError(NRouteError):
    """ML model training/inference failures."""

class ConfigError(NRouteError):
    """Invalid configuration."""
```

### 6.2 Error Handling Principles

| Principle                          | Implementation                                                     |
| ---------------------------------- | ------------------------------------------------------------------ |
| **Fail fast with clear messages**  | Validate inputs at API boundaries; raise typed exceptions with context. |
| **No silent failures**             | All caught exceptions logged via `structlog` before re-raising.    |
| **Graceful degradation**           | If RL model fails, fall back to Dijkstra with a warning log.       |
| **CLI error formatting**           | `rich` panel with error type, message, and suggestion for fix.     |
| **Exit codes**                     | 0 = success, 1 = input error, 2 = runtime error, 3 = model error. |

---

## 7. Performance Requirements

| Metric                             | Target                            | Measurement Method                  |
| ---------------------------------- | --------------------------------- | ----------------------------------- |
| **Route computation (Dijkstra)**   | ≤10ms for 500-node graph          | `pytest-benchmark`                  |
| **Route computation (RL)**         | ≤100ms for 500-node graph         | `pytest-benchmark`                  |
| **Congestion prediction (XGBoost)** | ≤50ms per link batch (100 links) | `pytest-benchmark`                  |
| **Anomaly detection**              | ≤10ms per sample                  | `pytest-benchmark`                  |
| **Simulation throughput**          | ≥100 ticks/sec for 1,000 nodes   | Simulation benchmark script         |
| **Topology generation**            | ≤2s for 1,000-node graph         | Unit test with timer                |
| **Memory (1,000 nodes)**           | ≤2GB peak                        | `tracemalloc` in integration tests  |
| **NetFlow ingestion**              | ≥10,000 records/sec              | Benchmark with sample data          |
| **CLI startup time**               | ≤1s (excluding model loading)    | Manual measurement                  |

---

## 8. Security Requirements

Since this is a local CLI/library tool (not a networked service), security scope is limited but still important:

| Area                          | Requirement                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------- |
| **Input Validation**          | All file inputs validated for format, size (max 500MB), and content before parsing. No arbitrary code execution from data files. |
| **Path Traversal**            | Output paths sanitized; no writing outside designated output directory.         |
| **Dependency Security**       | `pip-audit` integrated in CI to scan for known vulnerabilities in dependencies. |
| **Model Integrity**           | Bundled model files checksummed (SHA-256). Loader verifies checksum before deserializing. |
| **No Network Calls**          | The tool makes zero outbound network requests during normal operation. Fully air-gappable. |
| **Secrets**                   | No secrets, API keys, or credentials involved in V1.                           |

---

## 9. Testing Strategy

### 9.1 Test Pyramid

```
         ┌──────────┐
         │Benchmarks│  (3-5 tests — performance gates)
        ┌┴──────────┴┐
        │ Integration │  (10-15 tests — full pipelines)
       ┌┴────────────┴┐
       │   Unit Tests  │  (50-80 tests — individual functions)
       └──────────────┘
```

### 9.2 Test Categories

| Category        | Scope                                                        | Tools             | Run Frequency |
| --------------- | ------------------------------------------------------------ | ----------------- | ------------- |
| **Unit**        | Individual functions: parsers, algorithms, model predict()   | `pytest`          | Every commit  |
| **Integration** | CLI end-to-end, full simulation pipeline, data→route→export  | `pytest` + `click.testing` | Every PR |
| **Benchmark**   | Performance regression detection                             | `pytest-benchmark` | Weekly / release |
| **Type Check**  | Static type correctness                                      | `mypy --strict`   | Every commit  |
| **Lint**        | Code style and quality                                       | `ruff`            | Every commit  |
| **Coverage**    | ≥80% line coverage                                           | `pytest-cov`      | Every PR      |

### 9.3 Key Test Scenarios

| Test                                       | What It Validates                                                    |
| ------------------------------------------ | -------------------------------------------------------------------- |
| Dijkstra on known graph → expected path    | Classical algorithm correctness.                                     |
| RL router produces valid path (no loops)   | AI router outputs structurally valid routes.                         |
| RL router ≥ Dijkstra on congested topology | AI provides measurable improvement.                                  |
| Congestion predictor on synthetic data     | Predictions have ≥80% precision on test set.                         |
| Anomaly detector flags injected DDoS       | Detects known anomaly patterns.                                      |
| NetFlow parser on sample file              | Correct field extraction, no data loss.                              |
| CSV importer with malformed data           | Raises `IngestionError` with helpful message.                        |
| Simulation with link failure at tick 100   | Rerouting triggers, no packet black hole.                            |
| CLI `nroute simulate compare` output       | Correct table formatting, valid JSON export.                         |
| Seeded simulation produces identical results | Reproducibility guarantee.                                          |

---

## 10. CI/CD Pipeline

### 10.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ruff mypy
      - run: ruff check src/ tests/
      - run: mypy src/nroute --strict

  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ --cov=nroute --cov-report=xml -v
      - uses: codecov/codecov-action@v4

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pip-audit
      - run: pip-audit
```

### 10.2 Release Process

1. Tag release on `main` branch (`v1.0.0`).
2. GitHub Actions builds sdist + wheel.
3. Publishes to PyPI via `twine` (manual trigger / trusted publisher).
4. GitHub Release created with changelog.

---

## 11. Dependencies Summary

### Production Dependencies

```toml
[project]
dependencies = [
    "networkx>=3.2",
    "numpy>=1.26",
    "pandas>=2.1",
    "click>=8.1",
    "rich>=13.0",
    "pydantic>=2.5",
    "structlog>=24.1",
    "torch>=2.2",
    "stable-baselines3>=2.2",
    "gymnasium>=0.29",
    "scikit-learn>=1.4",
    "xgboost>=2.0",
    "matplotlib>=3.8",
    "plotext>=5.2",
    "scapy>=2.5",
    "joblib>=1.3",
    "pyyaml>=6.0",
]
```

### Development Dependencies

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-benchmark>=4.0",
    "mypy>=1.8",
    "ruff>=0.2",
    "pre-commit>=3.6",
    "pip-audit>=2.7",
]
```

---

## 12. Constraints & Technical Risks

### Constraints

| Constraint                           | Impact                                                          |
| ------------------------------------ | --------------------------------------------------------------- |
| CPU-only ML training                 | RL training on large topologies (>500 nodes) will be slow. Mitigated by pre-trained models and smaller training episodes. |
| NetworkX performance ceiling         | O(V²) memory for dense graphs. Adequate for ≤5,000 edges.      |
| Python GIL                           | Simulation is single-threaded. No parallel tick processing in V1. |
| No live data streaming               | V1 works on static/imported data only.                          |

### Technical Risks

| Risk                                      | Probability | Impact | Mitigation                                                    |
| ----------------------------------------- | ----------- | ------ | ------------------------------------------------------------- |
| RL agent fails to converge                | Medium      | High   | Fall back to heuristic-weighted Dijkstra; tune reward function; provide pre-trained weights. |
| pcap parsing is too slow for large files  | Medium      | Low    | Limit pcap support to first N flows; recommend NetFlow for large datasets. |
| Dependency conflicts (PyTorch + others)   | Low         | Medium | Pin compatible version ranges; test across Python versions in CI. |
| Simulation diverges on adversarial inputs | Low         | Medium | Input validation + simulation step limits + watchdog timer.   |

---

*End of TRD*
