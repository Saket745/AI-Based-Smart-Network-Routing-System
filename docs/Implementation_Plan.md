# Implementation Plan
# AI-Based Smart Network Routing System

**Version:** 1.0  
**Date:** June 11, 2026  
**Author:** Saket  
**Repository:** https://github.com/Saket745/AI-Based-Smart-Network-Routing-System  
**Companion Documents:**
- [PRD.md](file:///c:/Users/mssak/OneDrive/Desktop/Network%20Route%20Optimizer/PRD.md)
- [TRD.md](file:///c:/Users/mssak/OneDrive/Desktop/Network%20Route%20Optimizer/TRD.md)

---

## Build Philosophy

> **Rule:** Build bottom-up, verify each layer before building the next. Never build a feature that depends on an unverified layer below it.

The project has **10 phases**, each with:
- **Goal** — what this phase achieves.
- **Depends On** — which phases must be complete first.
- **Files Created/Modified** — exact file paths from the TRD project structure.
- **Tasks** — step-by-step implementation instructions.
- **Deliverables** — concrete, testable outputs.
- **Verification** — how to prove the phase is complete.

---

## Phase Dependency Graph

```
Phase 1: Project Scaffold & Tooling
    │
    ▼
Phase 2: Core Data Structures
    │
    ├──────────────────┐
    ▼                  ▼
Phase 3: Topology   Phase 4: Data
Engine              Ingestion
    │                  │
    └────────┬─────────┘
             ▼
Phase 5: Classical Routing Algorithms
             │
             ▼
Phase 6: Simulation Engine
             │
             ├──────────────────────────────┐
             ▼                              ▼
Phase 7: AI/ML Models              Phase 8: CLI Interface
(Congestion, Anomaly, RL)          (wraps Phases 2-7)
             │                              │
             └────────────┬─────────────────┘
                          ▼
Phase 9: Visualization & Export
                          │
                          ▼
Phase 10: Testing, Documentation & Release
```

---

## Phase 1: Project Scaffold & Tooling

**Goal:** Set up the project skeleton, packaging, CI pipeline, and developer tooling so that every subsequent phase starts with a working, lintable, testable codebase.

**Depends On:** Nothing (this is the root).

### Files Created

```
AI-Based-Smart-Network-Routing-System/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── nroute/
│       ├── __init__.py
│       └── __main__.py
├── tests/
│   └── conftest.py
├── data/                          (empty, with .gitkeep)
├── models/                        (empty, with .gitkeep)
└── scripts/                       (empty, with .gitkeep)
```

### Tasks

| #   | Task                                                                                              |
| --- | ------------------------------------------------------------------------------------------------- |
| 1.1 | Initialize git repo (if not already) and create `.gitignore` for Python (include `__pycache__`, `.venv`, `*.egg-info`, `dist/`, `build/`, `.mypy_cache`, `.ruff_cache`, `models/*.joblib`, `models/*.zip`, `output/`). |
| 1.2 | Create `pyproject.toml` with all production + dev dependencies from TRD §11. Set `[project.scripts]` entry point: `nroute = "nroute.cli.main:cli"`. Use `src` layout (`[tool.setuptools.packages.find] where = ["src"]`). Set `requires-python = ">=3.10"`. |
| 1.3 | Create `src/nroute/__init__.py` with version string `__version__ = "0.1.0"` and empty public API (placeholder imports that will be filled in later phases). |
| 1.4 | Create `src/nroute/__main__.py` with: `from nroute.cli.main import cli; cli()` — enables `python -m nroute`. |
| 1.5 | Create `LICENSE` file (MIT). |
| 1.6 | Create initial `README.md` with project name, one-line description from PRD, badges (placeholder), and "Under Development" notice. |
| 1.7 | Create `.pre-commit-config.yaml` with ruff (lint + format) and mypy hooks. |
| 1.8 | Create `.github/workflows/ci.yml` from TRD §10.1 (lint → type-check → test → coverage → security audit). |
| 1.9 | Create `tests/conftest.py` with basic fixtures: `tmp_path` alias, a small hardcoded test graph fixture (5 nodes, 7 edges with known weights). |
| 1.10 | Create empty placeholder directories: `data/`, `models/`, `scripts/` with `.gitkeep` files. |
| 1.11 | Create virtual environment, install project in editable mode (`pip install -e ".[dev]"`), verify `nroute --help` prints placeholder help text. |

### Deliverables

- [ ] `pip install -e ".[dev]"` succeeds without errors.
- [ ] `ruff check src/ tests/` passes.
- [ ] `mypy src/nroute` passes (with minimal stubs).
- [ ] `pytest tests/` runs (0 tests collected, 0 failures).
- [ ] `nroute --help` (or `python -m nroute --help`) prints a help message.

### Verification

```bash
pip install -e ".[dev]"
ruff check src/ tests/
mypy src/nroute --strict
pytest tests/ -v
python -m nroute --help
```

---

## Phase 2: Core Data Structures

**Goal:** Build the foundational data models that every other module depends on — `Topology`, `TrafficMatrix`, `FlowRecord`, `SimulationMetrics`, `RouteMetrics`, and configuration models.

**Depends On:** Phase 1.

### Files Created

```
src/nroute/
├── core/
│   ├── __init__.py
│   ├── topology.py          # Topology class
│   ├── traffic.py           # TrafficMatrix, FlowRecord
│   ├── metrics.py           # SimulationMetrics, RouteMetrics
│   └── config.py            # Pydantic NRouteConfig
├── utils/
│   ├── __init__.py
│   ├── logging.py           # structlog setup
│   ├── random.py            # SeededRandom manager
│   └── validators.py        # Input validation helpers
tests/
└── unit/
    └── test_topology.py
```

### Tasks

| #   | Task                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------- |
| 2.1 | **`utils/logging.py`** — Configure `structlog` with JSON and human-readable processors. Provide `get_logger(name)` factory function. |
| 2.2 | **`utils/random.py`** — Create `SeededRandom` class that wraps `random.Random` and `numpy.random.Generator` with a configurable seed. Provide module-level `get_rng(seed=None)` function. All randomness in the project must go through this. |
| 2.3 | **`utils/validators.py`** — Helper functions: `validate_node_id(id) -> str`, `validate_positive_float(value, name) -> float`, `validate_file_path(path, must_exist=True) -> Path`, `validate_probability(value) -> float` (must be 0.0-1.0). |
| 2.4 | **`core/config.py`** — Define `NRouteConfig` Pydantic model matching the YAML schema from TRD §5.1 (sections: `general`, `topology`, `simulation`, `ml`, `routing`, `export`). Add `load_config(path=None) -> NRouteConfig` that searches `./nroute.yaml` → `~/.nroute/config.yaml` → defaults. Add environment variable override support (`NROUTE_` prefix). |
| 2.5 | **`core/topology.py`** — Create `Topology` class wrapping `networkx.DiGraph`. Must support: (a) `add_node(id, **attrs)` / `add_edge(src, dst, **attrs)` with validation against the edge/node attribute schemas from TRD §4.1. (b) `remove_node(id)` / `remove_edge(src, dst)`. (c) `get_node(id)` / `get_edge(src, dst)` → typed dicts. (d) `nodes` / `edges` properties returning lists. (e) `node_count` / `edge_count` properties. (f) `neighbors(node_id)` → list of neighbor IDs. (g) `to_dict()` / `from_dict(data)` for serialization. (h) `save(path)` / `load(path)` for JSON persistence. (i) `summary()` → string with node/edge counts and attribute ranges. (j) `update_edge(src, dst, **attrs)` for dynamic topology updates. (k) `set_link_down(src, dst)` / `set_link_up(src, dst)` — sets status attribute. (l) `set_node_down(id)` / `set_node_up(id)`. (m) `copy()` → deep copy. |
| 2.6 | **`core/traffic.py`** — Define Pydantic models: `FlowRecord(source, destination, bytes, packets, duration, protocol, timestamp)` and `TrafficMatrix` (list of `FlowRecord` with helper methods: `from_csv(path)`, `from_dataframe(df)`, `to_dataframe()`, `filter_by_time(start, end)`, `summary()`). |
| 2.7 | **`core/metrics.py`** — Define Pydantic models: `RouteMetrics(path, total_latency, total_hops, bottleneck_bandwidth, bottleneck_utilization)` and `SimulationMetrics(tick, timestamp, throughput, avg_latency, packet_loss_rate, avg_utilization, reroute_count, active_flows)`. Add `MetricsCollectionResult` that holds a list of `SimulationMetrics` with aggregation methods: `mean_latency()`, `total_throughput()`, `peak_utilization()`, `to_dataframe()`, `to_json(path)`, `to_csv(path)`. |
| 2.8 | **`core/__init__.py`** — Export all public classes: `Topology`, `TrafficMatrix`, `FlowRecord`, `RouteMetrics`, `SimulationMetrics`, `MetricsCollectionResult`, `NRouteConfig`. |
| 2.9 | **`tests/unit/test_topology.py`** — Write tests: create topology, add/remove nodes and edges, validate attribute enforcement, serialization round-trip (save → load → compare), link up/down toggling, `summary()` output, `copy()` independence. Minimum 12 tests. |
| 2.10 | **Custom Exception Hierarchy** — Create `src/nroute/exceptions.py` with the exception classes from TRD §6.1: `NRouteError`, `TopologyError`, `IngestionError`, `RoutingError`, `SimulationError`, `ModelError`, `ConfigError`. Use these throughout all modules. |

### Deliverables

- [ ] `Topology` class fully functional with all methods listed above.
- [ ] `TrafficMatrix` and `FlowRecord` can parse CSV and serialize to DataFrame.
- [ ] `NRouteConfig` loads from YAML file and environment variables.
- [ ] `SimulationMetrics` and `RouteMetrics` can aggregate and export.
- [ ] All exceptions defined and importable.
- [ ] `pytest tests/unit/test_topology.py` — all tests pass.

### Verification

```bash
pytest tests/unit/test_topology.py -v
python -c "from nroute.core import Topology, TrafficMatrix, NRouteConfig; print('OK')"
python -c "from nroute.exceptions import NRouteError, TopologyError; print('OK')"
```

---

## Phase 3: Topology Engine (Synthetic Generation)

**Goal:** Build the topology generators — users can create random, scale-free, small-world, and fat-tree topologies with configurable parameters from TRD §4.1.

**Depends On:** Phase 2 (requires `Topology` class).

### Files Created

```
src/nroute/core/
└── generators.py            # Topology generators

tests/unit/
└── test_generators.py
```

### Tasks

| #   | Task                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------- |
| 3.1 | **`core/generators.py`** — Implement `TopologyGenerator` class with static methods: |
|     | (a) `random(n_nodes, edge_prob, **default_attrs) -> Topology` — Erdős–Rényi model via `nx.erdos_renyi_graph`. Assign random bandwidth (100-10000 Mbps), latency (1-50ms), default utilization=0.0, status="up" to each edge. |
|     | (b) `scale_free(n_nodes, **default_attrs) -> Topology` — Barabási-Albert model via `nx.barabasi_albert_graph`. |
|     | (c) `small_world(n_nodes, k_neighbors, rewire_prob, **default_attrs) -> Topology` — Watts-Strogatz via `nx.watts_strogatz_graph`. |
|     | (d) `fat_tree(k, **default_attrs) -> Topology` — Custom implementation of k-ary fat-tree data center topology (k/2 core, k pods, each pod has k/2 aggregation + k/2 edge switches, each edge switch has k/2 hosts). |
|     | (e) `from_adjacency_matrix(matrix, node_labels=None, **default_attrs) -> Topology` — Build from NumPy matrix. |
|     | (f) All generators must use `SeededRandom` from Phase 2 for reproducibility. |
|     | (g) All generators must set node attributes: `type` (based on topology role), `capacity` (random), `status="up"`. |
| 3.2 | Add a convenience class method to `Topology`: `Topology.generate(type, **kwargs) -> Topology` that dispatches to the appropriate generator. |
| 3.3 | **`tests/unit/test_generators.py`** — Test each generator: correct node/edge counts, correct attribute presence, fat-tree structural correctness (right number of core/agg/edge/host nodes), seeded reproducibility (same seed → same topology), edge cases (n=1, k=2). Minimum 10 tests. |

### Deliverables

- [ ] All 5 topology generators produce valid `Topology` objects.
- [ ] Fat-tree produces correct hierarchical structure.
- [ ] Seeded generation is reproducible.
- [ ] `Topology.generate("fat-tree", k=4)` works as shown in PRD §4.6.

### Verification

```bash
pytest tests/unit/test_generators.py -v
python -c "
from nroute.core import Topology
t = Topology.generate('fat-tree', k=4)
print(t.summary())
"
```

---

## Phase 4: Data Ingestion Engine

**Goal:** Build parsers for all supported data formats (CSV, JSON, NetFlow, pcap, SNMP) so topologies and traffic data can be imported from real-world sources.

**Depends On:** Phase 2 (requires `Topology`, `TrafficMatrix`, `FlowRecord`).

### Files Created

```
src/nroute/ingestion/
├── __init__.py
├── csv_json.py              # CSV/JSON importer
├── netflow.py               # NetFlow v5/v9 parser
├── pcap.py                  # pcap flow extractor
├── snmp.py                  # SNMP export parser
└── normalizer.py            # Common normalization layer

data/
├── sample_topology.json     # 10-node sample topology
├── sample_netflow.csv       # 100-row sample NetFlow data
└── sample_traffic.csv       # 200-row sample traffic matrix

tests/unit/
└── test_ingestion.py
```

### Tasks

| #   | Task                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------- |
| 4.1 | **`ingestion/normalizer.py`** — Create `Normalizer` class with: `normalize_topology(raw_nodes, raw_edges) -> Topology` (standardizes column names, validates types, fills missing attrs with defaults), `normalize_traffic(raw_records) -> TrafficMatrix` (standardizes fields, validates, creates `FlowRecord` objects). |
| 4.2 | **`ingestion/csv_json.py`** — Implement: (a) `CSVTopologyImporter.load(path) -> Topology` — expects columns: `src, dst` + optional `bandwidth, latency, jitter, packet_loss`. Auto-creates nodes from edge endpoints. (b) `JSONTopologyImporter.load(path) -> Topology` — expects `{"nodes": [...], "edges": [...]}` format. (c) `CSVTrafficImporter.load(path) -> TrafficMatrix` — expects columns: `source, destination, bytes, packets, duration, protocol, timestamp`. |
| 4.3 | **`ingestion/netflow.py`** — Implement `NetFlowParser.parse(path) -> TrafficMatrix`. Support CSV-exported NetFlow records (not raw binary in V1 — TRD scope). Columns: `src_addr, dst_addr, bytes, packets, first_switched, last_switched, protocol`. Map IPs to node IDs via normalizer. |
| 4.4 | **`ingestion/pcap.py`** — Implement `PcapParser.parse(path) -> TrafficMatrix`. Use `scapy.rdpcap()` to read pcap files. Extract per-flow summaries (5-tuple aggregation: src_ip, dst_ip, src_port, dst_port, protocol → sum bytes, packets, compute duration). Limit to first 100,000 packets for performance. |
| 4.5 | **`ingestion/snmp.py`** — Implement `SNMPParser.parse(path) -> Topology`. Parse CSV/JSON dumps with columns: `interface_id, in_octets, out_octets, speed, admin_status, oper_status`. Build topology edges from interface pairs. |
| 4.6 | **`ingestion/__init__.py`** — Provide a unified `ingest(path, format=None) -> Topology | TrafficMatrix` function that auto-detects format from file extension (`.csv`, `.json`, `.pcap`, `.nf`) and dispatches to the correct parser. |
| 4.7 | Add convenience methods to `Topology` class: `Topology.from_csv(path)`, `Topology.from_json(path)`, `Topology.from_netflow(path)` — these call the ingestion module. |
| 4.8 | Create sample data files in `data/`: `sample_topology.json` (10 nodes, 15 edges with realistic attrs), `sample_netflow.csv` (100 flow records), `sample_traffic.csv` (200 rows). |
| 4.9 | **`tests/unit/test_ingestion.py`** — Test: CSV round-trip (export topology → import → compare), JSON round-trip, NetFlow CSV parsing, malformed CSV raises `IngestionError`, missing columns raise descriptive errors, `ingest()` auto-detection works. Minimum 10 tests. |

### Deliverables

- [ ] All 5 parsers (CSV, JSON, NetFlow, pcap, SNMP) produce valid `Topology` or `TrafficMatrix` objects.
- [ ] `Topology.from_csv("data/sample_topology.csv")` works.
- [ ] `ingest("data/sample_netflow.csv")` auto-detects format and returns `TrafficMatrix`.
- [ ] Sample data files created and validated.
- [ ] Malformed input produces clear `IngestionError` messages.

### Verification

```bash
pytest tests/unit/test_ingestion.py -v
python -c "
from nroute.core import Topology
t = Topology.from_json('data/sample_topology.json')
print(t.summary())
"
```

---

## Phase 5: Classical Routing Algorithms

**Goal:** Implement Dijkstra, Bellman-Ford, and ECMP as baseline routing algorithms with a common `Router` interface so they can be swapped interchangeably with AI routers.

**Depends On:** Phase 2 (Topology), Phase 3 (generators for testing).

### Files Created

```
src/nroute/routing/
├── __init__.py
├── base.py                  # Abstract Router interface
├── dijkstra.py
├── bellman_ford.py
└── ecmp.py

tests/unit/
├── test_dijkstra.py
├── test_bellman_ford.py
└── test_ecmp.py
```

### Tasks

| #   | Task                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------- |
| 5.1 | **`routing/base.py`** — Define abstract base class `Router`: |
|     | (a) `__init__(self, topology: Topology, weight_metric: str = "latency")` |
|     | (b) Abstract method `compute_route(source: str, destination: str) -> RouteMetrics` |
|     | (c) Abstract method `compute_all_routes(source: str) -> dict[str, RouteMetrics]` |
|     | (d) Concrete method `compute_weight(edge_attrs: dict) -> float` that computes routing weight from edge attributes based on `weight_metric` (options: `latency`, `utilization`, `composite` = 0.5*latency + 0.3*utilization + 0.2/bandwidth). |
|     | (e) Concrete method `validate_path(path: list[str]) -> bool` — checks all edges exist, no loops, all links are "up". |
| 5.2 | **`routing/dijkstra.py`** — Implement `DijkstraRouter(Router)`. Use `networkx.dijkstra_path` with custom weight function from `compute_weight()`. Return `RouteMetrics` with computed total latency, hops, bottleneck bandwidth, bottleneck utilization. Handle unreachable destinations by raising `RoutingError`. |
| 5.3 | **`routing/bellman_ford.py`** — Implement `BellmanFordRouter(Router)`. Use `networkx.bellman_ford_path`. Same interface as Dijkstra. Must correctly handle negative weights (which Dijkstra cannot). Detect negative cycles and raise `RoutingError`. |
| 5.4 | **`routing/ecmp.py`** — Implement `ECMPRouter(Router)`. Find the k shortest equal-cost paths (configurable k, default=3). `compute_route()` returns the first path. Add method `compute_routes_multi(source, dest) -> list[RouteMetrics]` returning all k paths. Use `networkx.all_shortest_paths` or custom k-shortest-paths (Yen's algorithm). |
| 5.5 | **`routing/__init__.py`** — Export all routers. Add factory function `get_router(algorithm: str, topology: Topology) -> Router` that maps strings ("dijkstra", "bellman-ford", "ecmp") to router classes. |
| 5.6 | Add convenience method to `Topology`: `Topology.compute_routes(algorithm, source, destination)` that instantiates the right router and calls `compute_route()`. This matches the PRD §4.6 API example. |
| 5.7 | **Tests** — For each algorithm, test on the 5-node fixture from `conftest.py`: correct path, correct total latency, correct hop count, unreachable destination raises `RoutingError`, down-link avoidance, weight metric switching. ECMP: verify multiple paths returned. Minimum 8 tests per algorithm (24 total). |

### Deliverables

- [ ] All 3 routers implement the same `Router` interface.
- [ ] `DijkstraRouter` finds optimal shortest paths.
- [ ] `BellmanFordRouter` handles negative weights.
- [ ] `ECMPRouter` returns multiple equal-cost paths.
- [ ] `Topology.compute_routes(algorithm="dijkstra", source="A", destination="Z")` works as shown in PRD.
- [ ] Down links are avoided by all routers.

### Verification

```bash
pytest tests/unit/test_dijkstra.py tests/unit/test_bellman_ford.py tests/unit/test_ecmp.py -v
python -c "
from nroute.core import Topology
t = Topology.generate('random', n_nodes=20, edge_prob=0.3)
result = t.compute_routes(algorithm='dijkstra', source='0', destination='19')
print(f'Path: {result.path}, Latency: {result.total_latency}ms')
"
```

---

## Phase 6: Simulation Engine

**Goal:** Build the discrete-event simulation engine that generates traffic, routes it through the topology, injects failures, and collects per-tick metrics.

**Depends On:** Phase 2 (data structures), Phase 3 (topology generation), Phase 5 (routing algorithms).

### Files Created

```
src/nroute/simulation/
├── __init__.py
├── engine.py                # Main SimulationEngine
├── traffic_gen.py           # Traffic pattern generators
├── failure_injector.py      # Link/node failure injection
└── collector.py             # Metrics collection

tests/unit/
├── test_simulation.py
└── test_traffic_gen.py
```

### Tasks

| #   | Task                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------- |
| 6.1 | **`simulation/traffic_gen.py`** — Implement `TrafficGenerator` with traffic models: |
|     | (a) `uniform(topology, n_flows_per_tick) -> list[FlowRecord]` — Random source-destination pairs, random byte counts. |
|     | (b) `gravity(topology, n_flows_per_tick) -> list[FlowRecord]` — Flow probability proportional to node capacity product. |
|     | (c) `hotspot(topology, hotspot_nodes, n_flows_per_tick) -> list[FlowRecord]` — 80% of flows target hotspot nodes. |
|     | (d) `bursty(topology, n_flows_per_tick, burst_prob, burst_multiplier) -> list[FlowRecord]` — Periodic bursts of traffic. |
|     | (e) All generators use `SeededRandom` for reproducibility. |
| 6.2 | **`simulation/failure_injector.py`** — Implement `FailureInjector`: |
|     | (a) `schedule_link_failure(src, dst, tick)` — Mark link as "down" at specified tick. |
|     | (b) `schedule_node_failure(node_id, tick)` — Mark node + all its edges as "down". |
|     | (c) `schedule_latency_spike(src, dst, tick, multiplier, duration_ticks)` — Temporarily multiply latency. |
|     | (d) `schedule_recovery(src, dst, tick)` — Restore link to "up" at specified tick. |
|     | (e) `apply(topology, current_tick)` — Apply all scheduled events for the current tick. |
| 6.3 | **`simulation/collector.py`** — Implement `MetricsCollector`: |
|     | (a) `record_tick(tick, topology, active_flows, completed_flows, dropped_flows)` — Compute and store `SimulationMetrics` for this tick. |
|     | (b) `get_results() -> MetricsCollectionResult` — Return all collected metrics. |
|     | (c) Compute per-tick: throughput (bytes of completed flows / tick_duration), avg_latency (mean of completed flow latencies), packet_loss_rate (dropped / total), avg_utilization (mean of all link utilizations), reroute_count, active_flows. |
| 6.4 | **`simulation/engine.py`** — Implement `SimulationEngine` (the main loop from TRD §4.5): |
|     | (a) `__init__(self, topology, router, traffic_generator, failure_injector=None, config=None)` |
|     | (b) `run(duration_ticks: int, seed: int = None) -> MetricsCollectionResult` — Main simulation loop: |
|     | &nbsp;&nbsp;&nbsp;&nbsp; For each tick: (1) generate flows → (2) apply failures → (3) update utilizations → (4) route new flows → (5) forward existing flows (apply latency/loss) → (6) collect metrics → (7) advance clock. |
|     | (c) Track active flows with their current position, remaining hops, and accumulated latency. |
|     | (d) Apply packet loss probabilistically per hop based on edge `packet_loss` attribute. |
|     | (e) When a link goes down mid-flow, trigger rerouting via the router (increment `reroute_count`). |
|     | (f) Add progress bar via `rich` for long simulations. |
| 6.5 | **`simulation/__init__.py`** — Export `SimulationEngine`, `TrafficGenerator`, `FailureInjector`, `MetricsCollector`. |
| 6.6 | Add `Simulator` convenience class to `src/nroute/__init__.py` that matches the PRD §4.6 API: `Simulator(topology, algorithm, duration)` with `.run()` method. |
| 6.7 | **`tests/unit/test_traffic_gen.py`** — Test each traffic model produces valid flows, correct count, seeded reproducibility, hotspot actually biases toward hotspot nodes. Minimum 6 tests. |
| 6.8 | **`tests/unit/test_simulation.py`** — Test: (a) basic simulation runs without crash, (b) metrics are collected for every tick, (c) link failure causes reroute, (d) seeded simulation produces identical results, (e) dropped flows counted when no route exists, (f) simulation with 100 nodes runs under 10 seconds. Minimum 8 tests. |

### Deliverables

- [ ] `SimulationEngine.run()` completes a full simulation and returns `MetricsCollectionResult`.
- [ ] All 4 traffic models generate valid flows.
- [ ] `FailureInjector` correctly brings links down/up at scheduled ticks.
- [ ] Metrics correctly computed (throughput, latency, loss, utilization).
- [ ] Rerouting triggers on link failure.
- [ ] Seeded simulations are reproducible.

### Verification

```bash
pytest tests/unit/test_simulation.py tests/unit/test_traffic_gen.py -v
python -c "
from nroute.core import Topology
from nroute.routing import get_router
from nroute.simulation import SimulationEngine, TrafficGenerator

t = Topology.generate('random', n_nodes=30, edge_prob=0.2)
router = get_router('dijkstra', t)
traffic = TrafficGenerator('uniform', n_flows_per_tick=5)
sim = SimulationEngine(t, router, traffic)
results = sim.run(duration_ticks=100, seed=42)
print(f'Avg Latency: {results.mean_latency():.2f}ms')
print(f'Total Throughput: {results.total_throughput():.2f} bytes')
"
```

---

## Phase 7: AI/ML Models

**Goal:** Build the three AI components — congestion prediction (XGBoost), anomaly detection (Isolation Forest), and RL-based routing (PPO) — plus model persistence.

**Depends On:** Phase 2 (data structures), Phase 5 (routing interface), Phase 6 (simulation for RL training environment).

### Files Created

```
src/nroute/ml/
├── __init__.py
├── feature_eng.py           # Feature engineering
├── congestion.py            # Congestion prediction
├── anomaly.py               # Anomaly detection
├── rl_env.py                # Gymnasium RL environment
├── model_store.py           # Model save/load/version

src/nroute/routing/
└── rl_router.py             # RL-based Router

tests/unit/
├── test_congestion.py
├── test_anomaly.py
└── test_rl_router.py
```

### Tasks

| #   | Task                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------- |
| 7.1 | **`ml/feature_eng.py`** — Implement feature engineering functions: |
|     | (a) `extract_congestion_features(topology, traffic_history: list[TrafficMatrix]) -> pd.DataFrame` — For each link, compute the feature vector from TRD §4.3 (utilization_t, utilization_t-1..t-n, bandwidth, avg_latency, flow_count, hour_of_day, day_of_week, neighbor_utilization_avg). |
|     | (b) `extract_anomaly_features(traffic: TrafficMatrix) -> pd.DataFrame` — Compute features from TRD §4.4 (bytes_per_second, packets_per_second, flow_count, avg_packet_size, src_ip_entropy, dst_port_entropy, utilization_delta, latency_spike_flag). |
|     | (c) `create_congestion_labels(topology, threshold=0.85) -> np.ndarray` — Binary labels: 1 if utilization > threshold. |
| 7.2 | **`ml/congestion.py`** — Implement `CongestionPredictor`: |
|     | (a) `__init__(self, model_type="xgboost")` — Support "xgboost" and "lstm". |
|     | (b) `train(features: pd.DataFrame, labels: np.ndarray, epochs=100) -> dict` — Train model, return training metrics (accuracy, precision, recall, F1). |
|     | (c) `predict(features: pd.DataFrame) -> pd.DataFrame` — Return per-link predictions with columns: `link, congested (bool), probability (float)`. |
|     | (d) `save(path)` / `load(path)` — Persist trained model via `joblib` (XGBoost) or `torch.save` (LSTM). |
|     | (e) XGBoost implementation: `xgboost.XGBClassifier` with tuned hyperparams. |
|     | (f) LSTM implementation: PyTorch LSTM network with 2 layers, hidden_size=64, dropout=0.2. |
| 7.3 | **`ml/anomaly.py`** — Implement `AnomalyDetector`: |
|     | (a) `__init__(self, model_type="isolation_forest")` — Support "isolation_forest" and "autoencoder". |
|     | (b) `fit(features: pd.DataFrame)` — Train on normal traffic data. |
|     | (c) `detect(features: pd.DataFrame) -> pd.DataFrame` — Return per-sample: `anomaly_score (0-1), is_anomaly (bool), anomaly_type (str)`. |
|     | (d) Anomaly type classification heuristic: if `bytes_per_second` extremely high + low `src_ip_entropy` → "DDoS". If sudden `utilization_delta` spike → "link_failure". If `flow_count` drops to 0 → "black_hole". |
|     | (e) `save(path)` / `load(path)`. |
| 7.4 | **`ml/rl_env.py`** — Implement `NetworkRoutingEnv(gymnasium.Env)` from TRD §4.2: |
|     | (a) State space: flattened feature vector of all node and edge attributes. |
|     | (b) Action space: `gymnasium.spaces.Discrete(max_neighbors)` with action masking for invalid hops. |
|     | (c) Reward function: `α × (1/latency) + β × throughput - γ × packet_loss - δ × path_length` (configurable hyperparams). |
|     | (d) `reset()` → set random source-destination pair, return initial state. |
|     | (e) `step(action)` → move to next hop, update utilization, return (state, reward, terminated, truncated, info). Terminate when destination reached or max_hops exceeded. |
|     | (f) Integration with `Topology` and `TrafficGenerator` for realistic environment dynamics. |
| 7.5 | **`routing/rl_router.py`** — Implement `RLRouter(Router)`: |
|     | (a) `__init__(self, topology, algorithm="ppo")` — Support "ppo" and "dqn". |
|     | (b) `train(traffic_data=None, episodes=1000, seed=None) -> dict` — Train the RL agent using `stable-baselines3`. Return training metrics (mean_reward, convergence_episode). Use the simulation engine as the training environment. |
|     | (c) `compute_route(source, destination) -> RouteMetrics` — Use trained agent to greedily select next-hops from source to destination. |
|     | (d) `save(path)` / `load(path)` — Persist via `stable-baselines3` model save. |
|     | (e) Fallback: if model not trained or inference fails, log warning and delegate to `DijkstraRouter`. |
| 7.6 | **`ml/model_store.py`** — Implement `ModelStore`: |
|     | (a) `save_model(model, name, version, path) -> str` — Save model with metadata (name, version, timestamp, checksum). |
|     | (b) `load_model(name, version=None, path=None) -> object` — Load model; if version=None, load latest. Verify SHA-256 checksum. |
|     | (c) `list_models(path) -> list[dict]` — List all saved models with metadata. |
| 7.7 | **`ml/__init__.py`** — Export `CongestionPredictor`, `AnomalyDetector`, `NetworkRoutingEnv`, `ModelStore`. |
| 7.8 | Update `src/nroute/routing/__init__.py` to include "rl" in the `get_router()` factory. |
| 7.9 | Create `AIRouter` convenience class in `src/nroute/__init__.py` matching PRD §4.6 API: wraps `RLRouter` + `CongestionPredictor` + `AnomalyDetector`. Methods: `train()`, `compute_routes()`, `predict_congestion()`, `detect_anomalies()`. |
| 7.10 | **Tests**: |
|     | `test_congestion.py` — Train XGBoost on synthetic data, verify predictions, save/load round-trip. Minimum 5 tests. |
|     | `test_anomaly.py` — Fit Isolation Forest on normal data, inject anomalous samples, verify detection. Minimum 5 tests. |
|     | `test_rl_router.py` — Train RL agent for 50 episodes on small topology (5 nodes), verify it produces valid paths (no loops, all edges exist), verify fallback to Dijkstra when untrained. Minimum 5 tests. |

### Deliverables

- [ ] `CongestionPredictor` trains and predicts with ≥80% precision on synthetic data.
- [ ] `AnomalyDetector` flags injected anomalies with ≥90% detection rate.
- [ ] `RLRouter` trains and produces valid (loop-free) routes.
- [ ] `RLRouter` falls back to Dijkstra gracefully when untrained.
- [ ] `AIRouter` facade works as shown in PRD §4.6.
- [ ] All models save/load with checksum verification.

### Verification

```bash
pytest tests/unit/test_congestion.py tests/unit/test_anomaly.py tests/unit/test_rl_router.py -v
python -c "
from nroute.core import Topology
from nroute import AIRouter

t = Topology.generate('random', n_nodes=10, edge_prob=0.4)
router = AIRouter(model='rl-ppo', topology=t)
# Quick training
router.train(episodes=50)
result = router.compute_routes(source='0', destination='9')
print(f'AI Path: {result.path}')
"
```

---

## Phase 8: CLI Interface

**Goal:** Build the full CLI using Click, wrapping all functionality from Phases 2-7 with rich terminal output.

**Depends On:** Phases 2-7 (wraps everything).

### Files Created

```
src/nroute/cli/
├── __init__.py
├── main.py                  # Root Click group
├── topology_cmd.py          # nroute topology {generate,import,show}
├── route_cmd.py             # nroute route compute
├── simulate_cmd.py          # nroute simulate {run,compare}
├── train_cmd.py             # nroute train
├── predict_cmd.py           # nroute predict congestion
├── detect_cmd.py            # nroute detect anomalies
└── export_cmd.py            # nroute export

tests/integration/
└── test_cli.py
```

### Tasks

| #   | Task                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------- |
| 8.1 | **`cli/main.py`** — Create root Click group `cli` with `--version`, `--config`, `--verbose`, `--seed` global options. Add ASCII banner on `--help`. Register all subcommand groups. |
| 8.2 | **`cli/topology_cmd.py`** — Implement: |
|     | `nroute topology generate --type {random,fat-tree,scale-free,small-world} --nodes N --edge-prob P --k K --output PATH --seed SEED` |
|     | `nroute topology import --file PATH --format {csv,json,netflow,pcap,snmp} --output PATH` |
|     | `nroute topology show --file PATH` — Print topology summary as rich table. |
| 8.3 | **`cli/route_cmd.py`** — Implement: |
|     | `nroute route compute --topology PATH --algorithm {dijkstra,bellman-ford,ecmp,rl} --source ID --destination ID --weight {latency,utilization,composite}` — Print path and metrics. |
| 8.4 | **`cli/simulate_cmd.py`** — Implement: |
|     | `nroute simulate run --topology PATH --algorithm ALG --traffic {uniform,gravity,hotspot,bursty} --duration TICKS --flows-per-tick N --failures-file PATH --output PATH --seed SEED` — Run simulation, print summary, save results. |
|     | `nroute simulate compare --topology PATH --algorithms ALG1,ALG2,... --traffic MODEL --duration TICKS --output PATH --seed SEED` — Run same simulation with multiple algorithms, print side-by-side comparison table. |
| 8.5 | **`cli/train_cmd.py`** — Implement: |
|     | `nroute train --model {congestion,anomaly,rl} --data PATH --topology PATH --epochs N --output PATH` — Train specified model and save weights. |
| 8.6 | **`cli/predict_cmd.py`** — Implement: |
|     | `nroute predict congestion --topology PATH --model PATH --horizon MINUTES --traffic PATH` — Run prediction, print per-link congestion probabilities as rich table. |
| 8.7 | **`cli/detect_cmd.py`** — Implement: |
|     | `nroute detect anomalies --traffic PATH --model PATH --threshold FLOAT` — Run detection, print anomalies as rich table with scores and types. |
| 8.8 | **`cli/export_cmd.py`** — Implement: |
|     | `nroute export --input PATH --format {json,csv,png,svg} --output PATH` — Convert results between formats, generate plots. |
| 8.9 | **Error handling** — All commands wrap execution in try/except. On `NRouteError` subclasses, print a rich error panel with the error type, message, and a suggested fix. Use exit codes from TRD §6.2. |
| 8.10 | **`tests/integration/test_cli.py`** — Use `click.testing.CliRunner` to test: topology generate (verify output file), topology show (verify table output), route compute (verify path printed), simulate run (verify metrics output), export json (verify file created). Test error cases: missing file, invalid algorithm. Minimum 10 tests. |

### Deliverables

- [ ] All CLI commands from PRD §4.5 are functional.
- [ ] `nroute --help` shows all commands with descriptions.
- [ ] Each command has `--help` with documented options.
- [ ] Errors display rich formatted panels with suggestions.
- [ ] Exit codes follow TRD convention.

### Verification

```bash
pytest tests/integration/test_cli.py -v
nroute --help
nroute topology generate --type random --nodes 20 --output test_topo.json
nroute topology show --file test_topo.json
nroute route compute --topology test_topo.json --algorithm dijkstra --source 0 --destination 19
nroute simulate run --topology test_topo.json --algorithm dijkstra --duration 100 --output results.json
```

---

## Phase 9: Visualization & Export

**Goal:** Build matplotlib plot generators, terminal-based charts, and structured data exporters.

**Depends On:** Phase 6 (simulation results), Phase 7 (prediction/detection results).

### Files Created

```
src/nroute/visualization/
├── __init__.py
├── plots.py                 # Matplotlib plot generators
├── terminal.py              # Rich/plotext terminal visualizations
└── exporters.py             # JSON/CSV export utilities

tests/unit/
└── test_visualization.py
```

### Tasks

| #   | Task                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------- |
| 9.1 | **`visualization/plots.py`** — Implement plot generators using matplotlib: |
|     | (a) `plot_throughput(results: MetricsCollectionResult, output: Path)` — Throughput over time line chart. |
|     | (b) `plot_latency(results, output)` — Average latency over time. |
|     | (c) `plot_utilization_heatmap(results, topology, output)` — Heatmap of link utilizations at a specific tick or averaged. |
|     | (d) `plot_comparison(results_dict: dict[str, MetricsCollectionResult], output)` — Multi-line overlay comparing algorithms. |
|     | (e) `plot_congestion_timeline(predictions, output)` — Congestion probability over time per link. |
|     | (f) `plot_anomaly_scores(detections, output)` — Anomaly scores with threshold line. |
|     | (g) All plots: configurable DPI, format (png/svg/pdf), title, dark theme option. |
| 9.2 | **`visualization/terminal.py`** — Implement terminal visualizations: |
|     | (a) `print_topology_summary(topology)` — Rich table with node/edge details. |
|     | (b) `print_route(route_metrics)` — Rich panel showing path, latency, hops. |
|     | (c) `print_simulation_summary(results)` — Rich table with key metrics. |
|     | (d) `print_comparison_table(results_dict)` — Side-by-side comparison of algorithms. |
|     | (e) `print_congestion_table(predictions)` — Table of per-link congestion probabilities. |
|     | (f) `print_anomaly_table(detections)` — Table of anomaly scores and types. |
|     | (g) `plot_inline(data, title)` — Use `plotext` for inline terminal charts. |
| 9.3 | **`visualization/exporters.py`** — Implement export utilities: |
|     | (a) `export_json(data, path)` — Export any results to JSON (uses Pydantic `.model_dump()`). |
|     | (b) `export_csv(data, path)` — Export metrics DataFrame to CSV. |
|     | (c) `export_topology(topology, path, format)` — Export topology as JSON or CSV edge list. |
|     | (d) `export_report(results, topology, output_dir)` — Generate a complete report directory: `metrics.json`, `metrics.csv`, `throughput.png`, `latency.png`, `utilization_heatmap.png`, `summary.txt`. |
| 9.4 | Wire `results.plot_throughput()`, `results.export()` etc. on `MetricsCollectionResult` to call these visualization functions (add methods to the metrics class from Phase 2). |
| 9.5 | **`tests/unit/test_visualization.py`** — Test: plot functions don't crash (generate to temp file), export JSON is valid JSON, export CSV is valid CSV, terminal print functions produce output. Minimum 8 tests. |

### Deliverables

- [ ] 6 matplotlib plot types generate valid image files.
- [ ] Terminal tables render correctly via rich.
- [ ] JSON and CSV exports produce valid, parseable files.
- [ ] `export_report()` generates a complete output directory.
- [ ] `results.plot_throughput()` works as shown in PRD.

### Verification

```bash
pytest tests/unit/test_visualization.py -v
python -c "
from nroute.core import Topology
from nroute.routing import get_router
from nroute.simulation import SimulationEngine, TrafficGenerator
from nroute.visualization import export_report

t = Topology.generate('random', n_nodes=20, edge_prob=0.2)
router = get_router('dijkstra', t)
traffic = TrafficGenerator('uniform', n_flows_per_tick=3)
sim = SimulationEngine(t, router, traffic)
results = sim.run(duration_ticks=50, seed=42)
export_report(results, t, './output/test_report')
print('Report generated in ./output/test_report/')
"
```

---

## Phase 10: Testing, Documentation & Release

**Goal:** Achieve ≥80% test coverage, write comprehensive documentation, train and bundle baseline models, create sample data scripts, and prepare for PyPI release.

**Depends On:** All previous phases.

### Files Created / Modified

```
tests/
├── integration/
│   ├── test_full_pipeline.py    # End-to-end pipeline tests
│   └── test_real_data.py        # Tests with sample data files
├── benchmarks/
│   ├── bench_routing.py         # Routing performance benchmarks
│   └── bench_simulation.py      # Simulation performance benchmarks

scripts/
├── generate_sample_data.py      # Generate sample datasets
└── train_baseline_models.py     # Train and save baseline models

models/                           # Pre-trained model weights
├── congestion_xgb_v1.joblib
├── anomaly_iforest_v1.joblib
└── rl_ppo_v1.zip

docs/
├── api_reference.md             # API documentation
├── quickstart.md                # Getting started guide
├── examples.md                  # Usage examples
└── contributing.md              # Contribution guidelines

README.md                        # Updated with full documentation
CHANGELOG.md                     # Version history
```

### Tasks

| #    | Task                                                                                                            |
| ---- | --------------------------------------------------------------------------------------------------------------- |
| 10.1 | **Integration Tests** — `test_full_pipeline.py`: Test complete workflows: (a) Generate topology → route → simulate → export JSON. (b) Import CSV → AI route → predict congestion → export. (c) Generate topology → inject failures → simulate with RL → compare vs Dijkstra. (d) Full CLI pipeline: `topology generate` → `simulate run` → `export`. Minimum 6 tests. |
| 10.2 | **Integration Tests** — `test_real_data.py`: Run ingestion + routing + simulation on the sample data files in `data/`. Verify no crashes, valid output. Minimum 3 tests. |
| 10.3 | **Benchmarks** — `bench_routing.py`: Benchmark Dijkstra, Bellman-Ford, ECMP, RL on 50/100/500/1000-node topologies. Verify Dijkstra ≤10ms at 500 nodes, RL ≤100ms at 500 nodes. |
| 10.4 | **Benchmarks** — `bench_simulation.py`: Benchmark simulation throughput on 100/500/1000-node topologies. Verify ≥100 ticks/sec at 1000 nodes. |
| 10.5 | **`scripts/generate_sample_data.py`** — Script that generates: `data/sample_topology.json` (50 nodes), `data/sample_traffic.csv` (1000 flows), `data/sample_netflow.csv` (500 NetFlow records), `data/large_topology.json` (500 nodes for benchmarking). |
| 10.6 | **`scripts/train_baseline_models.py`** — Script that: (a) Generates training data by running simulations on various topologies. (b) Trains XGBoost congestion predictor → saves to `models/congestion_xgb_v1.joblib`. (c) Trains Isolation Forest anomaly detector → saves to `models/anomaly_iforest_v1.joblib`. (d) Trains PPO RL agent for 10,000 episodes → saves to `models/rl_ppo_v1.zip`. |
| 10.7 | **Coverage Check** — Run `pytest --cov=nroute --cov-report=html` and verify ≥80% line coverage. Add tests for any uncovered code paths. |
| 10.8 | **Documentation — `docs/quickstart.md`** — Write getting started guide: installation, first topology generation, first route computation, first simulation, first AI routing. Include copy-pasteable code snippets. |
| 10.9 | **Documentation — `docs/api_reference.md`** — Document every public class and method: `Topology`, `Simulator`, `AIRouter`, `CongestionPredictor`, `AnomalyDetector`, all CLI commands. Include parameter descriptions, return types, and examples. |
| 10.10 | **Documentation — `docs/examples.md`** — Write 5 complete examples: (a) Compare Dijkstra vs RL on a fat-tree. (b) Predict congestion on imported NetFlow data. (c) Detect anomalies in traffic logs. (d) Simulate link failures and measure resilience. (e) Use as a library in a custom SDN script. |
| 10.11 | **Documentation — `docs/contributing.md`** — Contribution guidelines: setup, code style (ruff), type checking (mypy), testing requirements, PR process. |
| 10.12 | **Update `README.md`** — Add: project overview, feature list, installation instructions, quickstart code, CLI usage examples, API usage examples, architecture diagram (from TRD), benchmark results, contributing section, license. Add badges: CI status, coverage, Python versions, PyPI version (placeholder). |
| 10.13 | **Create `CHANGELOG.md`** — Document v0.1.0 release with all features. |
| 10.14 | **Update `pyproject.toml`** — Add classifiers, project URLs, long description from README, `[project.scripts]` entry point. Verify `python -m build` produces valid wheel and sdist. |
| 10.15 | **Final Validation** — Run the complete CI pipeline locally: `ruff check` → `mypy --strict` → `pytest --cov` → `pip-audit` → `python -m build`. All must pass. |

### Deliverables

- [ ] ≥80% test coverage (unit + integration).
- [ ] Benchmarks pass performance targets from TRD §7.
- [ ] Pre-trained models bundled in `models/`.
- [ ] Sample data files in `data/`.
- [ ] Complete documentation in `docs/`.
- [ ] README with installation, usage, and examples.
- [ ] `python -m build` produces valid wheel.
- [ ] Full CI pipeline passes.

### Verification

```bash
# Run everything
ruff check src/ tests/
mypy src/nroute --strict
pytest tests/ --cov=nroute --cov-report=term-missing -v
pytest tests/benchmarks/ --benchmark-only
pip-audit
python -m build

# Verify installable
pip install dist/nroute-0.1.0-py3-none-any.whl
nroute --version
nroute topology generate --type fat-tree --k 4 --output test.json
nroute simulate run --topology test.json --algorithm dijkstra --duration 100
```

---

## Summary: Build Order Checklist

| Phase | Name                             | Est. Effort  | Key Output                                  |
| ----- | -------------------------------- | ------------ | ------------------------------------------- |
| **1** | Project Scaffold & Tooling       | 2-3 hours    | Working project skeleton, CI pipeline        |
| **2** | Core Data Structures             | 4-6 hours    | Topology, TrafficMatrix, Metrics, Config     |
| **3** | Topology Engine                  | 3-4 hours    | 5 topology generators                        |
| **4** | Data Ingestion                   | 4-5 hours    | 5 format parsers + sample data               |
| **5** | Classical Routing                | 3-4 hours    | Dijkstra, Bellman-Ford, ECMP                 |
| **6** | Simulation Engine                | 6-8 hours    | Full simulation loop with traffic + failures |
| **7** | AI/ML Models                     | 8-12 hours   | Congestion, Anomaly, RL routing              |
| **8** | CLI Interface                    | 4-6 hours    | All nroute commands                          |
| **9** | Visualization & Export           | 3-4 hours    | Plots, terminal output, exporters            |
| **10** | Testing, Docs & Release         | 6-8 hours    | 80%+ coverage, docs, pre-trained models      |
|       | **Total**                        | **43-60 hrs** |                                              |

---

## How to Use This Plan With AI

Feed all three documents (PRD, TRD, Implementation Plan) to your AI coding agent, then use this prompt:

> "Read all documents carefully. Do not start coding yet. Summarize what you understood, identify any missing details, and confirm the build plan. After that, we will build the app **phase by phase** — start with Phase 1 only."

After Phase 1 is verified, proceed:

> "Phase 1 is complete and verified. Proceed to Phase 2. Build all files listed, implement all tasks, and run the verification steps."

Repeat for each phase.

---

*End of Implementation Plan*
