# DATASET_GENERATOR_SPEC.md

## 1. Overview
The Dataset Generator collects snapshots of the network topology and traffic states during simulations. It outputs human-readable development snapshots in JSON format, which are subsequently aggregated and saved in efficient Parquet datasets for training.

---

## 2. Simulation Trace Collection & JSON Snapshots
During simulation, a telemetry snapshot is taken at each tick. The snapshot includes:
1. **Topology structure**: List of nodes and edges with their static/dynamic attributes.
2. **Traffic states**: Flow records active during the tick (packet volumes, latency, drops).
3. **Labels**: Congestion status for each link (utilization >= 0.85).

### JSON Snapshot Schema
```json
{
  "tick": 42,
  "nodes": [
    {"id": "A", "capacity": 1000.0, "status": "up"},
    {"id": "B", "capacity": 1000.0, "status": "up"}
  ],
  "edges": [
    {"source": "A", "destination": "B", "bandwidth": 1000.0, "latency": 5.0, "utilization": 0.35, "packet_loss": 0.0, "status": "up"}
  ],
  "traffic": [
    {"source": "A", "destination": "B", "bytes": 350000, "packets": 240, "protocol": "TCP", "status": "delivered"}
  ]
}
```

---

## 3. Parquet Dataset Construction
To scale to large topologies and long simulations, the dataset generator compiles individual JSON snapshots into tabular dataframes stored as Parquet files:
* **`node_features.parquet`**: Tick, node ID, capacity, status, degree, queue length, packet load, centrality scores.
* **`edge_features.parquet`**: Tick, source, destination, bandwidth, latency, utilization, loss, reliability, congestion label.
* **`global_metrics.parquet`**: Tick, throughput, average latency, overall packet loss rate.

---

## 4. Train / Validation / Test Splits
Splits are performed using two distinct strategies:
1. **Temporal Split (default)**: Splits the simulation timeline (e.g., first 70% of ticks for training, next 15% for validation, final 15% for testing).
2. **Topology-based Split**: Trains GNN on a set of generated topologies (e.g., Erdős-Rényi) and tests generalization on unseen topologies (e.g., Fat-Tree).
