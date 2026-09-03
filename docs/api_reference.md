# API Reference — nroute Core Modules

This document provides a comprehensive API Reference for the `nroute` Python packages.

---

## 1. Digital Twin & Pre-Flight Validation (`nroute.simulation`)

### `nroute.simulation.digital_twin.DigitalTwinEngine`
The central orchestration facade for the Network Digital Twin platform.
* **`DigitalTwinEngine(snapshot_dir: Path | None = None)`**
  * Initializes the Digital Twin engine instance.
* **`load_topology(path: str | Path) -> None`**
  * Loads and normalizes a baseline topology JSON file.
* **`ingest_config(path: str | Path) -> None`**
  * Ingests OpenConfig device configuration and updates the twin state.
* **`compute_reachability() -> dict[str, set[str]]`**
  * Computes the complete pairwise reachability matrix across all active nodes.
* **`simulate_change(change: ConfigChange, weight: str = "latency") -> ChangeImpactResult`**
  * Computes deterministic blast-radius metrics (path shifts, unreachable pairs, latency delta).
* **`validate_change(change: ConfigChange | str | Path, policy: PolicyGateConfig | str | Path | None = None, weight: str = "latency") -> ValidationResult`**
  * Executes end-to-end pre-flight policy validation returning PASS, WARN, or BLOCK.

---

### `nroute.simulation.validator.PreFlightValidator`
Deterministic declarative safety policy evaluation engine.
* **`PreFlightValidator(policy: PolicyGateConfig | None = None)`**
  * Initializes the validator with a declarative policy gate configuration.
* **`validate(baseline: Topology, change: ConfigChange, engine: ChangeImpactSimulator | None = None, weight: str = "latency") -> ValidationResult`**
  * Evaluates proposed change against policy thresholds and returns a structured `ValidationResult`.

---

### `nroute.simulation.policy.PolicyGateConfig`
Pydantic model defining declarative pre-flight safety gates.
* **Attributes**:
  * `max_latency_increase_ms: float` (Default: `10.0`) — Warning threshold for latency delta.
  * `max_path_changed_ratio: float` (Default: `0.20`) — Warning threshold for rerouted traffic paths.
  * `allow_newly_unreachable_pairs: bool` (Default: `False`) — If `False`, severed reachability triggers `BLOCK`.
  * `protected_nodes: list[str]` — Critical nodes that must remain connected; disconnection triggers `BLOCK`.
  * `max_affected_nodes: int | None` — Maximum permissible number of impacted nodes.
  * `max_affected_edges: int | None` — Maximum permissible number of impacted edges.

---

### `nroute.core.openconfig.ConfigChange`
Declarative network configuration patch model.
* **Attributes**:
  * `change_id: str` — Unique identifier for change tracking and audit logging.
  * `target_devices: list[str]` — List of network devices targeted by the change.
  * `node_state_changes: dict[str, str]` — Node administrative state modifications (`"up"` / `"down"`).
  * `edge_state_changes: dict[tuple[str, str], str]` — Link administrative state modifications (`"up"` / `"down"`).
  * `cost_metric_overrides: dict[tuple[str, str], float]` — Edge metric/weight adjustments.

---

## 2. Core Data Models (`nroute.core`)

### `nroute.core.topology.Topology`
Represents the network graph topology with graph query methods.
* **`Topology(graph: nx.DiGraph | None = None)`**
  * Initializes an empty topology or wraps an existing NetworkX directed graph.
* **`load(path: str | Path) -> Topology`** *(classmethod)*
  * Loads a topology configuration from a JSON file.
* **`save(path: str | Path) -> None`**
  * Saves the current topology configuration to a JSON file.
* **`from_netflow(netflow_path: str | Path) -> Topology`** *(classmethod)*
  * Ingests NetFlow records from a CSV file to dynamically discover nodes and edges.
* **Properties**:
  * `node_count: int` — Total number of nodes in the network.
  * `edge_count: int` — Total number of unidirectional links in the network.
  * `nodes: KeysView` — Access all nodes in the topology.
  * `edges: EdgeView` — Access all unidirectional edges in the topology.

---

## 3. Deterministic Routing Engines (`nroute.routing`)

### `nroute.routing.base.BaseRouter`
The base interface for all pathfinding engines.
* **`compute_path(topology: Topology, source: str, destination: str, weight: str | Callable | None = None) -> list[str]`**
  * Calculates the optimal route from source to destination.

### `nroute.routing.dijkstra.DijkstraRouter`
High-performance shortest path computation using Dijkstra's algorithm.
* **`compute_path(topology: Topology, source: str, destination: str, weight: str | Callable | None = "latency") -> list[str]`**
  * Computes deterministic single-path routes.

### `nroute.routing.ecmp.ECMPRouter`
Equal-Cost Multi-Path router for balanced flow distribution.
* **`compute_paths(topology: Topology, source: str, destination: str, weight: str | None = "latency") -> list[list[str]]`**
  * Returns all equal-cost candidate paths between source and destination.

---

## 4. Simulation Engine (`nroute.simulation`)

### `nroute.simulation.engine.SimulationEngine`
Packet-level network simulation execution, failure injections, queue updates, and metric tracking.
* **`SimulationEngine(topology: Topology, router: BaseRouter, traffic_gen: TrafficGenerator)`**
  * Initializes the simulation manager.
* **`run(duration_ticks: int = 100, seed: int | None = None) -> MetricsCollectionResult`**
  * Runs discrete-event simulation for a specific duration.

---

## 5. Auxiliary Research Modules (`nroute.ml`)

*Preserved empirical baseline research models:*
* **`CongestionPredictor(model_type: str = "xgboost")`** — Predicts link congestion from flow telemetry.
* **`AnomalyDetector(model_type: str = "isolation_forest")`** — Identifies network anomalies.
* **`RLRouter(topology: Topology, algorithm: str = "ppo")`** — Historical reinforcement learning pathfinder.
