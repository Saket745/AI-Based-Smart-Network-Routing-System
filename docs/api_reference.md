# API Reference — nroute Core Modules

This document provides a comprehensive API Reference for the `nroute` Python packages.

---

## 1. Core Data Models (`nroute.core`)

### `nroute.core.topology.Topology`
Represents the network graph topology, providing methods for loading, saving, and querying nodes and edges.
* **`Topology(graph: nx.DiGraph | None = None)`**
  * Initializes an empty topology or wraps an existing NetworkX directed graph.
* **`load(path: str | Path) -> Topology`** *(classmethod)*
  * Loads a topology configuration from a JSON file.
* **`save(path: str | Path) -> None`**
  * Saves the current topology configuration to a JSON file.
* **`from_netflow(netflow_path: str | Path) -> Topology`** *(classmethod)*
  * Ingests NetFlow records from a CSV file to dynamically discover nodes, edges, and traffic matrices.
* **Properties**:
  * `node_count: int` — Total number of nodes in the network.
  * `edge_count: int` — Total number of unidirectional links in the network.
  * `nodes: KeysView` — Access all nodes in the topology.
  * `edges: EdgeView` — Access all unidirectional edges in the topology.

### `nroute.core.traffic.TrafficMatrix`
Represents a snapshot of active traffic flows traversing the network topology.
* **`from_csv(path: str | Path) -> TrafficMatrix`** *(classmethod)*
  * Loads traffic flow records from a CSV file.
* **`to_csv(path: str | Path) -> None`**
  * Saves the active traffic flow matrix to a CSV file.
* **`add_flow(flow: FlowRecord) -> None`**
  * Adds an individual flow record to the traffic matrix.

---

## 2. Routing Engines (`nroute.routing`)

### `nroute.routing.base.BaseRouter`
The base class interface for all pathfinding and routing engines.
* **`compute_path(topology: Topology, source: str, destination: str, weight: str | Callable | None = None) -> list[str]`**
  * Abstract method to calculate the route from source to destination. Returns a list of node IDs.

### `nroute.routing.dijkstra.DijkstraRouter`
Computes the shortest path using Dijkstra's algorithm.
* **`compute_path(topology: Topology, source: str, destination: str, weight: str | Callable | None = "weight") -> list[str]`**
  * Standard shortest-path computations supporting link cost attribute optimization.

### `nroute.routing.rl_router.RLRouter`
A deep reinforcement learning routing agent powered by Stable-Baselines3 (PPO or DQN).
* **`RLRouter(topology: Topology | None = None, algorithm: str = "ppo", confidence_threshold: float = 0.4)`**
  * Initializes the RL-based path finder with automatic fallback capabilities.
* **`train(traffic_data: Any = None, episodes: int = 1000, seed: int | None = None) -> dict[str, Any]`**
  * Trains the policy on the network topology Gymnasium environment.
* **`save(path: str) -> None`**
  * Serializes trained policy weights (using PyTorch state dictionaries or SB3 archives) and caches training topology structure.
* **`load(path: str) -> None`**
  * Re-loads policy weights and structure metadata from disk.

---

## 3. Simulation Engine (`nroute.simulation`)

### `nroute.simulation.engine.SimulationEngine`
Manages packet-level network simulation execution, failure injections, queue updates, and metric tracking.
* **`SimulationEngine(topology: Topology, router: BaseRouter, traffic_gen: TrafficGenerator)`**
  * Initializes the simulation manager.
* **`run(duration_ticks: int = 100, seed: int | None = None) -> SimulationResult`**
  * Runs the simulation for a specific duration.
* **`apply_change(change: ConfigChange) -> None`**
  * Dynamically modifies simulation properties (e.g. topology edits) during execution.

### `nroute.simulation.traffic_gen.TrafficGenerator`
Abstract base class for simulating network traffic generation patterns.
* **`TrafficGenerator(model: str = "uniform", n_flows_per_tick: int = 5)`**
  * Base traffic injector support.
* **Available Models**: `"uniform"`, `"gravity"`, `"hotspot"`, `"bursty"`.

---

## 4. Machine Learning & Anomaly Detection (`nroute.ml`)

### `nroute.ml.congestion.CongestionPredictor`
Predicts link congestion levels using scikit-learn/XGBoost or custom models.
* **`CongestionPredictor(model_type: str = "xgboost")`**
  * Initializes the predictor.
* **`train(features: pd.DataFrame, labels: np.ndarray) -> dict[str, float]`**
  * Fits the classifier and returns training metrics.
* **`predict(features: pd.DataFrame) -> pd.DataFrame`**
  * Infers congestion probability for live links.

### `nroute.ml.anomaly.AnomalyDetector`
Identifies malicious traffic anomalies or network performance degradation.
* **`AnomalyDetector(model_type: str = "isolation_forest", contamination: float = 0.05)`**
  * Configures the detector.
* **`fit(features: pd.DataFrame) -> None`**
  * Trains the anomaly detection engine on normal operational traffic.
* **`predict(features: pd.DataFrame) -> np.ndarray`**
  * Classifies features as normal (0) or anomalous (1).

---

## 5. Exporters (`nroute.visualization.exporters`)

Provides methods to serialize topologies and metrics.
* **`JSONExporter`** — Serializes graph details, nodes, and links to JSON format.
* **`CSVExporter`** — Writes flat node and edge attribute tables to CSV files.
* **`GraphMLExporter`** — Generates standard XML GraphML files compatible with external visualization tools like Gephi.
