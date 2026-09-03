# Quickstart Guide — nroute CLI

Welcome to the **nroute** Quickstart! `nroute` is a high-performance Network Digital Twin and Pre-Flight Change-Impact Validation Platform designed to model network topologies, simulate proposed configuration changes, and validate safety policies prior to production deployment.

---

## 1. Installation

To install `nroute` and its dependencies in a local environment:

```bash
# Clone the repository
git clone https://github.com/Saket745/AI-Based-Smart-Network-Routing-System.git
cd AI-Based-Smart-Network-Routing-System

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

### Step 2.1: Pre-Flight Change Validation

The primary capability of NRoute is deterministic change validation. Given a baseline topology, a proposed change patch, and a declarative safety policy, NRoute calculates the blast radius and returns a **PASS**, **WARN**, or **BLOCK** verdict.

* **Execute pre-flight change validation**:
  ```bash
  nroute twin validate \
    --topology data/sample_topology.json \
    --change changes/proposed_change.yaml \
    --policy policies/safety_policy.yaml
  ```

* **Emit machine-readable JSON for CI/CD pipelines**:
  ```bash
  nroute twin validate \
    -t data/sample_topology.json \
    -ch changes/proposed_change.yaml \
    -p policies/safety_policy.yaml \
    --json \
    --output reports/preflight_result.json
  ```

* **Enforce strict warnings in automation** (returns exit code 2 on WARN verdicts):
  ```bash
  nroute twin validate \
    -t data/sample_topology.json \
    -ch changes/proposed_change.yaml \
    -p policies/safety_policy.yaml \
    --strict-warnings
  ```

---

### Step 2.2: Managing Topologies
Load, generate, and inspect network topologies.

* **Generate a synthetic Fat-Tree data-center topology**:
  ```bash
  nroute topology generate --type fat-tree --k 4 --output data/fat_tree.json
  ```

* **Inspect summary statistics of a topology file**:
  ```bash
  nroute topology show --file data/sample_topology.json
  ```

---

### Step 2.3: Computing Network Routes
Calculate paths through your network using deterministic pathfinding algorithms.

* **Calculate a path using Dijkstra's shortest path**:
  ```bash
  nroute route compute --topology data/sample_topology.json --source "0" --destination "9" --algorithm dijkstra
  ```

* **Calculate multi-path routes using Equal-Cost Multi-Path (ECMP)**:
  ```bash
  nroute route compute --topology data/sample_topology.json --source "0" --destination "9" --algorithm ecmp
  ```

---

### Step 2.4: Running Network Simulations & Failure Injection
Simulate traffic flows and link packet queues under realistic load models with dynamic failure injection.

* **Run a 100-tick simulation with Dijkstra routing**:
  ```bash
  nroute simulate run \
    --topology data/sample_topology.json \
    --algorithm dijkstra \
    --duration 100 \
    --traffic-model uniform \
    --output output/simulation_results.json
  ```

* **Inject a link failure during simulation**:
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

### Step 2.5: Digital Twin Diagnostics & Reachability

* **Compute full pairwise reachability matrix**:
  ```bash
  nroute twin reachability --topology data/sample_topology.json
  ```

* **Simulate standalone config change impact**:
  ```bash
  nroute twin impact \
    --topology data/sample_topology.json \
    --change changes/proposed_change.yaml
  ```

---

### Step 2.6: Starting the Digital Twin REST API

Launch the FastAPI Digital Twin REST server for web consumption or CI/CD integration:

```bash
# Start API server on localhost:8000
nroute api start --host 127.0.0.1 --port 8000
```

> **Note**: When running locally without configuring `NROUTE_API_TOKEN`, the server automatically generates a temporary session token and prints it to the console for easy Bearer authentication.

---

### Step 2.7: Historical Research & Auxiliary ML Tooling

The repository includes completed empirical research on machine learning and heuristic models (preserved as benchmark baselines under `artifacts/`):

* **Train baseline congestion prediction model**:
  ```bash
  nroute train congestion --topology data/sample_topology.json --output models/congestion_xgb.joblib
  ```

* **Train baseline anomaly detection model**:
  ```bash
  nroute train anomaly --topology data/sample_topology.json --output models/anomaly_iforest.joblib
  ```
