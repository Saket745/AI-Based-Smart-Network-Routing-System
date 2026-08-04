# Quickstart Guide — nroute CLI

Welcome to the **nroute** CLI Quickstart! `nroute` is a CLI-driven, AI-based smart network routing platform that simulates, predicts, and detects issues in network topologies using machine learning models.

---

## 1. Installation

To install `nroute` and its dependencies in a local environment:

```bash
# Clone the repository
git clone https://github.com/your-username/nroute.git
cd nroute

# Create a virtual environment and activate it
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies and the CLI in editable mode
pip install -e .
```

Verify your installation:

```bash
nroute --help
```

---

## 2. Step-by-Step CLI Walkthrough

### Step 2.1: Managing Topologies
You can load, generate, and inspect network topologies.

* **Generate a random topology** (e.g., 50 nodes):
  ```bash
  nroute topology generate --nodes 50 --edge-prob 0.1 --output data/generated_topology.json
  ```

* **Inspect summary statistics** of a topology file:
  ```bash
  nroute topology info --topology data/sample_topology.json
  ```

---

### Step 2.2: Computing Network Routes
Calculate paths through your network using traditional routing algorithms.

* **Calculate a path using Dijkstra's shortest path**:
  ```bash
  nroute route compute --topology data/sample_topology.json --src "0" --dst "9" --algorithm dijkstra
  ```

* **Calculate a path using Bellman-Ford or ECMP**:
  ```bash
  nroute route compute --topology data/sample_topology.json --src "0" --dst "9" --algorithm bellman-ford
  ```

---

### Step 2.3: Running Traffic Simulations
Simulate traffic flows and link packet queues under realistic load models.

* **Run a 100-tick simulation** with Dijkstra routing:
  ```bash
  nroute simulate run \
    --topology data/sample_topology.json \
    --algorithm dijkstra \
    --duration 100 \
    --traffic-model uniform \
    --output output/simulation_results.json
  ```

* **Inject a link failure** during the run to evaluate dynamic rerouting:
  ```bash
  nroute simulate run \
    --topology data/sample_topology.json \
    --algorithm dijkstra \
    --duration 100 \
    --fail-link "0,2" \
    --fail-tick 30 \
    --output output/failure_sim_results.json
  ```

---

### Step 2.4: Training Baseline Models
Train XGBoost, Isolation Forest, GNNs, and RL agents on network topologies.

* **Train XGBoost congestion prediction model**:
  ```bash
  nroute train congestion \
    --topology data/sample_topology.json \
    --model-type xgboost \
    --output models/congestion_xgb_v1.joblib
  ```

* **Train Isolation Forest anomaly detector**:
  ```bash
  nroute train anomaly \
    --topology data/sample_topology.json \
    --model-type isolation_forest \
    --output models/anomaly_iforest_v1.joblib
  ```

* **Train PPO Reinforcement Learning routing agent**:
  ```bash
  nroute train rl \
    --topology data/sample_topology.json \
    --algorithm ppo \
    --timesteps 2000 \
    --output models/rl_ppo_v1.zip
  ```

* **Train Graph Neural Network (GCN/GraphSAGE)**:
  ```bash
  nroute train gnn \
    --topology data/sample_topology.json \
    --model-type gcn \
    --epochs 10 \
    --output-dir models/gnn
  ```

---

### Step 2.5: ML Inference & Anomaly Detection

* **Predict Congestion** on links:
  ```bash
  nroute predict congestion \
    --model models/congestion_xgb_v1.joblib \
    --allow-unsafe \
    --features-csv data/sample_traffic.csv
  ```

* **Detect Traffic Anomalies**:
  ```bash
  nroute detect anomalies \
    --model models/anomaly_iforest_v1.joblib \
    --allow-unsafe \
    --features-csv data/sample_netflow.csv
  ```

---

### Step 2.6: Exporting Network Metrics
Export topology stats, routing paths, or simulation metrics to CSV, JSON, or GraphML formats.

* **Export to CSV**:
  ```bash
  nroute export --topology data/sample_topology.json --format csv --output output/topology_export.csv
  ```

* **Export to GraphML** (for importing into tools like Gephi):
  ```bash
  nroute export --topology data/sample_topology.json --format graphml --output output/topology_network.graphml
  ```

---

### Step 2.7: Launching a Digital Twin
Deploy a simulated twin network environment that mirrors the active topology.

```bash
nroute twin start --topology data/sample_topology.json --sync-interval 5
```
