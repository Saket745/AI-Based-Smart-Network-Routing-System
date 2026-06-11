# Multi-Agent AI System Architecture
# Network Route Optimization

**Version:** 1.0  
**Date:** June 11, 2026  
**Author:** Saket  
**Repository:** https://github.com/Saket745/AI-Based-Smart-Network-Routing-System  
**Companion Docs:** [PRD](file:///c:/Users/mssak/OneDrive/Desktop/Network%20Route%20Optimizer/PRD.md) · [TRD](file:///c:/Users/mssak/OneDrive/Desktop/Network%20Route%20Optimizer/TRD.md) · [Implementation Plan](file:///c:/Users/mssak/OneDrive/Desktop/Network%20Route%20Optimizer/Implementation_Plan.md)

---

## 1. System Overview

The multi-agent architecture decomposes network route optimization into **7 specialized agents**, each owning a distinct responsibility. An **Orchestrator Agent** coordinates the entire pipeline, routing tasks, validating outputs, and driving feedback loops until convergence.

```mermaid
graph TB
    subgraph External["External Inputs"]
        RT["Real-Time Traffic Data<br/>(NetFlow / SNMP / pcap)"]
        ST["Synthetic Topology<br/>(Generated)"]
        UC["User Commands<br/>(CLI / Library API)"]
    end

    subgraph Orchestrator["🎯 ORCHESTRATOR AGENT"]
        ORC["Task Router &<br/>Lifecycle Manager"]
    end

    subgraph Agents["Specialized Agents"]
        TA["🏗️ Topology Agent"]
        DA["📥 Data Ingestion Agent"]
        RA["🛤️ Routing Agent"]
        PA["🔮 Prediction Agent"]
        AA["🛡️ Anomaly Agent"]
        SA["⚙️ Simulation Agent"]
        VA["📊 Validation Agent"]
    end

    subgraph Outputs["System Outputs"]
        OP["Optimized Routes"]
        AL["Anomaly Alerts"]
        CP["Congestion Predictions"]
        MR["Metrics & Reports"]
        RR["Reroute Commands"]
    end

    UC --> ORC
    RT --> ORC
    ST --> ORC

    ORC --> TA
    ORC --> DA
    ORC --> RA
    ORC --> PA
    ORC --> AA
    ORC --> SA
    ORC --> VA

    VA -->|"Feedback Loop"| ORC

    RA --> OP
    AA --> AL
    PA --> CP
    SA --> MR
    ORC --> RR

    style Orchestrator fill:#1a1a2e,stroke:#e94560,stroke-width:3px,color:#eee
    style TA fill:#16213e,stroke:#0f3460,color:#eee
    style DA fill:#16213e,stroke:#0f3460,color:#eee
    style RA fill:#16213e,stroke:#0f3460,color:#eee
    style PA fill:#16213e,stroke:#0f3460,color:#eee
    style AA fill:#16213e,stroke:#0f3460,color:#eee
    style SA fill:#16213e,stroke:#0f3460,color:#eee
    style VA fill:#e94560,stroke:#1a1a2e,stroke-width:2px,color:#fff
```

---

## 2. Agent Definitions

### 2.1 🎯 Orchestrator Agent

The brain of the system. Receives all tasks, decomposes them, dispatches to specialist agents, collects results, and drives feedback loops.

| Property          | Detail                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Role**          | Central coordinator — task decomposition, routing, lifecycle management, and convergence control. |
| **Inputs**        | User commands (CLI/API), real-time traffic data, agent results, validation feedback.          |
| **Outputs**       | Task assignments to agents, final aggregated results, reroute commands, escalation alerts.    |
| **State**         | Task queue, agent status registry, convergence metrics, retry counters, global config.        |

**Decision Logic:**

```mermaid
flowchart TD
    START["Receive Task / Event"] --> CLASSIFY{"Classify<br/>Task Type"}

    CLASSIFY -->|"New Topology"| TOPO["Dispatch to<br/>Topology Agent"]
    CLASSIFY -->|"Import Data"| INGEST["Dispatch to<br/>Data Ingestion Agent"]
    CLASSIFY -->|"Compute Route"| ROUTE["Dispatch to<br/>Routing Agent"]
    CLASSIFY -->|"Predict Congestion"| PRED["Dispatch to<br/>Prediction Agent"]
    CLASSIFY -->|"Detect Anomaly"| ANOM["Dispatch to<br/>Anomaly Agent"]
    CLASSIFY -->|"Run Simulation"| SIM["Dispatch to<br/>Simulation Agent"]
    CLASSIFY -->|"Compound Task"| DECOMP["Decompose into<br/>Sub-Tasks"]

    DECOMP --> DEPS{"Resolve<br/>Dependencies"}
    DEPS --> PARALLEL["Execute Independent<br/>Sub-Tasks in Parallel"]
    DEPS --> SEQUENTIAL["Queue Dependent<br/>Sub-Tasks"]

    TOPO --> VALIDATE["Send Results to<br/>Validation Agent"]
    INGEST --> VALIDATE
    ROUTE --> VALIDATE
    PRED --> VALIDATE
    ANOM --> VALIDATE
    SIM --> VALIDATE
    PARALLEL --> VALIDATE

    VALIDATE --> CHECK{"Validation<br/>Passed?"}
    CHECK -->|"Yes"| AGGREGATE["Aggregate &<br/>Return Results"]
    CHECK -->|"No"| FEEDBACK{"Retry<br/>Count < Max?"}
    FEEDBACK -->|"Yes"| REFINE["Refine Parameters &<br/>Re-Dispatch"]
    FEEDBACK -->|"No"| ESCALATE["Escalate: Use<br/>Fallback Strategy"]

    REFINE --> CLASSIFY
    ESCALATE --> FALLBACK["Apply Fallback<br/>(e.g., Dijkstra)"]
    FALLBACK --> AGGREGATE

    style START fill:#e94560,color:#fff
    style AGGREGATE fill:#0f3460,color:#fff
    style ESCALATE fill:#ff6b6b,color:#fff
```

---

### 2.2 🏗️ Topology Agent

Owns all topology operations — generation, mutation, and state management.

| Property          | Detail                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Role**          | Build, manage, and mutate network topologies (synthetic or imported).                        |
| **Inputs**        | Generation parameters (type, node count, edge probability), or raw data from Ingestion Agent. |
| **Outputs**       | `Topology` object with validated node/edge attributes.                                       |
| **Decision Logic** | Select generator based on type → validate structural properties → assign default attributes → return. |

**Capabilities:**
- Generate: random, scale-free, small-world, fat-tree topologies.
- Mutate: add/remove nodes and edges, toggle link status (up/down), inject latency spikes.
- Validate: ensure graph is connected (or report components), no self-loops, attributes within valid ranges.
- Snapshot: save topology state for rollback during simulation.

---

### 2.3 📥 Data Ingestion Agent

Parses and normalizes external network data into the internal representation.

| Property          | Detail                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Role**          | Import, parse, validate, and normalize network data from external sources.                   |
| **Inputs**        | Raw files (CSV, JSON, NetFlow, pcap, SNMP exports) + format hint.                            |
| **Outputs**       | Normalized `Topology` and/or `TrafficMatrix` objects.                                        |
| **Decision Logic** | Auto-detect format → select parser → parse → normalize → validate → return or raise `IngestionError`. |

**Error Handling:**
- Malformed files → `IngestionError` with line number and expected format.
- Missing required columns → descriptive error listing missing fields.
- Oversized files (>500MB) → reject with size limit message.
- Partial parse success → return valid records + warning log of skipped rows.

---

### 2.4 🛤️ Routing Agent

Computes optimal routes using classical or AI-based algorithms.

| Property          | Detail                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Role**          | Compute optimal paths between nodes using the selected routing algorithm.                    |
| **Inputs**        | `Topology`, source node, destination node, algorithm selection, weight metric.               |
| **Outputs**       | `RouteMetrics` (path, total latency, hops, bottleneck bandwidth/utilization).                |
| **Decision Logic** | Select algorithm → compute route → validate path (no loops, all links up) → return or fallback. |

**Algorithm Selection Logic:**

```mermaid
flowchart TD
    REQ["Route Request"] --> ALG{"Selected<br/>Algorithm?"}

    ALG -->|"dijkstra"| DIJ["Dijkstra<br/>(Shortest Path)"]
    ALG -->|"bellman-ford"| BF["Bellman-Ford<br/>(Neg. Weights)"]
    ALG -->|"ecmp"| ECMP["ECMP<br/>(K-Shortest Paths)"]
    ALG -->|"rl"| RL_CHECK{"RL Model<br/>Trained?"}

    RL_CHECK -->|"Yes"| RL["RL Agent<br/>(PPO/DQN Inference)"]
    RL_CHECK -->|"No"| FALLBACK["⚠️ Fallback to<br/>Dijkstra + Warning"]

    DIJ --> VALID{"Path<br/>Valid?"}
    BF --> VALID
    ECMP --> VALID
    RL --> VALID
    FALLBACK --> VALID

    VALID -->|"Yes"| METRICS["Compute<br/>RouteMetrics"]
    VALID -->|"No Path Exists"| ERR["Raise<br/>RoutingError"]

    METRICS --> RETURN["Return Result"]

    style REQ fill:#0f3460,color:#fff
    style ERR fill:#ff6b6b,color:#fff
    style FALLBACK fill:#ffa502,color:#000
    style RETURN fill:#2ed573,color:#000
```

**Fallback Chain:** RL → Weighted Dijkstra → Unweighted BFS → RoutingError.

---

### 2.5 🔮 Prediction Agent

Forecasts future network congestion using ML models.

| Property          | Detail                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Role**          | Predict per-link congestion probability N minutes into the future.                           |
| **Inputs**        | Current `Topology` state, historical `TrafficMatrix` data, prediction horizon (minutes).     |
| **Outputs**       | Per-link congestion predictions: `{link_id, congested: bool, probability: float}`.           |
| **Decision Logic** | Extract features → select model (XGBoost/LSTM) → predict → threshold → flag at-risk links.  |

**Feature Pipeline:**

```mermaid
flowchart LR
    RAW["Raw Traffic<br/>+ Topology State"] --> FE["Feature<br/>Engineering"]

    FE --> F1["utilization_t"]
    FE --> F2["utilization_history<br/>(window=12)"]
    FE --> F3["bandwidth"]
    FE --> F4["avg_latency"]
    FE --> F5["flow_count"]
    FE --> F6["temporal features<br/>(hour, day)"]
    FE --> F7["neighbor_utilization_avg"]

    F1 & F2 & F3 & F4 & F5 & F6 & F7 --> MODEL{"Model<br/>Selection"}

    MODEL -->|"Tabular"| XGB["XGBoost<br/>Classifier"]
    MODEL -->|"Sequential"| LSTM["LSTM<br/>Network"]

    XGB --> PRED["Predictions<br/>(probability per link)"]
    LSTM --> PRED

    PRED --> THRESH{"prob > 0.75?"}
    THRESH -->|"Yes"| ALERT["🚨 Congestion<br/>Alert"]
    THRESH -->|"No"| OK["✅ Normal"]

    ALERT --> ORC_NOTIFY["Notify Orchestrator<br/>→ Trigger Reroute"]

    style ALERT fill:#ff6b6b,color:#fff
    style OK fill:#2ed573,color:#000
```

**Training Loop:**
1. Simulation Agent generates historical traffic data.
2. Feature engineering extracts training features.
3. Model trains with cross-validation (80/20 split).
4. Validation Agent checks precision ≥80%, recall ≥75%.
5. If metrics fail → adjust hyperparameters → retrain (max 3 iterations).

---

### 2.6 🛡️ Anomaly Agent

Detects abnormal traffic patterns in real-time or batch mode.

| Property          | Detail                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Role**          | Detect DDoS floods, link failures, traffic black holes, and other anomalies.                 |
| **Inputs**        | `TrafficMatrix` (current or historical), trained anomaly model.                              |
| **Outputs**       | Per-sample: `{anomaly_score: 0-1, is_anomaly: bool, anomaly_type: str}`.                    |
| **Decision Logic** | Extract features → run Isolation Forest/Autoencoder → score → classify anomaly type → alert. |

**Anomaly Classification Heuristics:**

| Pattern | Anomaly Type | Action |
|---------|-------------|--------|
| High `bytes_per_second` + low `src_ip_entropy` | **DDoS Flood** | Block + reroute |
| Sudden `utilization_delta` spike (>3σ) | **Link Degradation** | Reduce weight, reroute |
| `flow_count` drops to 0 on active link | **Traffic Black Hole** | Mark link down, reroute |
| `latency_spike_flag` = true + high jitter | **Link Failure** | Failover to backup path |

---

### 2.7 ⚙️ Simulation Agent

Runs discrete-event simulations of the entire network under various conditions.

| Property          | Detail                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Role**          | Execute network simulations with traffic generation, failure injection, and metrics collection. |
| **Inputs**        | `Topology`, routing algorithm, traffic model, failure schedule, duration, seed.               |
| **Outputs**       | `MetricsCollectionResult` (per-tick throughput, latency, loss, utilization, reroute count).   |
| **Decision Logic** | Initialize → per-tick loop (generate → fail → route → forward → collect) → aggregate → report. |

**Simulation Tick Loop:**

```mermaid
flowchart TD
    INIT["Initialize<br/>Simulation"] --> TICK["Tick N"]

    TICK --> GEN["1. Generate<br/>Traffic Flows"]
    GEN --> FAIL["2. Apply Scheduled<br/>Failures"]
    FAIL --> UPDATE["3. Update Topology<br/>Utilizations"]
    UPDATE --> ROUTE_NEW["4. Route New Flows<br/>(via Routing Agent)"]
    ROUTE_NEW --> FORWARD["5. Forward Existing<br/>Flows (apply latency/loss)"]
    FORWARD --> COLLECT["6. Collect Metrics<br/>(throughput, latency, loss)"]
    COLLECT --> ADVANCE["7. Advance Clock"]

    ADVANCE --> DONE{"tick == max_ticks<br/>or converged?"}
    DONE -->|"No"| TICK
    DONE -->|"Yes"| AGG["Aggregate Metrics<br/>& Generate Report"]

    AGG --> VALIDATE_SIM["Send to<br/>Validation Agent"]

    style INIT fill:#0f3460,color:#fff
    style AGG fill:#2ed573,color:#000
```

---

### 2.8 📊 Validation Agent

The quality gate. Every agent result passes through validation before being accepted.

| Property          | Detail                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- |
| **Role**          | Verify correctness, quality, and performance of all agent outputs.                           |
| **Inputs**        | Agent results + validation criteria (from config or task metadata).                          |
| **Outputs**       | `{valid: bool, issues: list[str], suggestions: list[str]}`.                                  |
| **Decision Logic** | Apply domain-specific validation rules → pass/fail → generate feedback for retry if failed.  |

**Validation Rules by Agent:**

| Agent              | Validation Checks                                                                     |
| ------------------ | ------------------------------------------------------------------------------------- |
| **Topology Agent** | Graph connected? Attributes in valid ranges? No self-loops? Node/edge counts match request? |
| **Ingestion Agent** | All required fields present? Data types correct? No NaN in critical fields? Size within limits? |
| **Routing Agent**  | Path exists in topology? No loops? All links "up"? Latency computation correct? |
| **Prediction Agent** | Precision ≥80%? Recall ≥75%? Probabilities in [0,1]? No NaN predictions? |
| **Anomaly Agent**  | Detection rate ≥90% on known anomalies? False positive rate ≤5%? Scores in [0,1]? |
| **Simulation Agent** | Metrics non-negative? Throughput > 0? No NaN values? Duration matches request? |

---

## 3. Complete Task Flow — End-to-End Pipeline

This flowchart shows how a complete network optimization request flows through all agents:

```mermaid
flowchart TD
    USER["👤 User Request:<br/>'Optimize routing on this network'"] --> ORC["🎯 Orchestrator:<br/>Decompose Task"]

    ORC --> STEP1["Step 1: Build/Import Topology"]
    STEP1 --> TA_WORK["🏗️ Topology Agent<br/>or<br/>📥 Ingestion Agent"]

    TA_WORK --> VA1["📊 Validate Topology"]
    VA1 -->|"❌ Fail"| TA_FIX["Fix: Regenerate with<br/>adjusted parameters"]
    TA_FIX --> TA_WORK
    VA1 -->|"✅ Pass"| STEP2

    STEP2["Step 2: Baseline Routing"] --> RA_CLASSICAL["🛤️ Routing Agent<br/>(Dijkstra baseline)"]

    RA_CLASSICAL --> VA2["📊 Validate Routes"]
    VA2 -->|"❌ No valid routes"| TOPO_FIX["Topology Agent:<br/>Increase connectivity"]
    TOPO_FIX --> TA_WORK
    VA2 -->|"✅ Pass"| STEP3

    STEP3["Step 3: Generate Training Data"] --> SA_TRAIN["⚙️ Simulation Agent<br/>(Run baseline simulation)"]

    SA_TRAIN --> STEP4["Step 4: Train AI Models<br/>(Parallel)"]

    STEP4 --> PA_TRAIN["🔮 Prediction Agent<br/>Train Congestion Model"]
    STEP4 --> AA_TRAIN["🛡️ Anomaly Agent<br/>Train Anomaly Detector"]
    STEP4 --> RL_TRAIN["🛤️ Routing Agent<br/>Train RL Model"]

    PA_TRAIN --> VA3["📊 Validate Models"]
    AA_TRAIN --> VA3
    RL_TRAIN --> VA3

    VA3 -->|"❌ Metrics below target"| RETRAIN["Adjust Hyperparams<br/>& Retrain"]
    RETRAIN --> STEP4
    VA3 -->|"✅ All models pass"| STEP5

    STEP5["Step 5: AI-Optimized Simulation"] --> SA_AI["⚙️ Simulation Agent<br/>(RL routing + predictions<br/>+ anomaly detection)"]

    SA_AI --> VA4["📊 Validate: AI ≥ 15%<br/>better than baseline?"]
    VA4 -->|"❌ No improvement"| TUNE["Tune RL reward<br/>function & retrain"]
    TUNE --> RL_TRAIN
    VA4 -->|"✅ Improvement confirmed"| STEP6

    STEP6["Step 6: Generate Results"] --> RESULTS["📊 Export Reports<br/>Metrics + Plots + Alerts"]

    RESULTS --> FINAL["✅ Return to User:<br/>Optimized routes, predictions,<br/>anomaly alerts, comparison report"]

    style USER fill:#e94560,color:#fff
    style FINAL fill:#2ed573,color:#000
    style VA1 fill:#ffa502,color:#000
    style VA2 fill:#ffa502,color:#000
    style VA3 fill:#ffa502,color:#000
    style VA4 fill:#ffa502,color:#000
```

---

## 4. Feedback Loop Mechanisms

The system uses **three types of feedback loops** to ensure quality and convergence:

### 4.1 Immediate Validation Loop (Per-Task)

Every agent result is validated before acceptance. If validation fails, parameters are refined and the agent re-executes.

```mermaid
flowchart LR
    AGENT["Agent Executes<br/>Task"] --> RESULT["Agent Output"]
    RESULT --> VA["Validation<br/>Agent"]
    VA -->|"✅ Pass"| ACCEPT["Accept &<br/>Return"]
    VA -->|"❌ Fail"| REFINE["Refine<br/>Parameters"]
    REFINE --> AGENT

    style VA fill:#ffa502,color:#000
```

**Convergence Rule:** Max 3 retries per task. After 3 failures → escalate to fallback strategy.

### 4.2 Model Retraining Loop (ML Agents)

When model performance degrades below thresholds, automatic retraining is triggered.

```mermaid
flowchart TD
    PREDICT["Run Predictions"] --> EVAL["Evaluate<br/>Against Ground Truth"]
    EVAL --> CHECK{"Precision ≥ 80%<br/>AND Recall ≥ 75%?"}
    CHECK -->|"Yes"| CONTINUE["Continue Using<br/>Current Model"]
    CHECK -->|"No"| RETRAIN["Retrain with<br/>Updated Data"]
    RETRAIN --> EVAL

    CONTINUE --> DRIFT{"Periodic Drift<br/>Check (every 100 ticks)"}
    DRIFT -->|"Drift Detected"| RETRAIN
    DRIFT -->|"Stable"| CONTINUE

    style CHECK fill:#ffa502,color:#000
```

### 4.3 Optimization Convergence Loop (System-Level)

The full pipeline iterates until AI routing demonstrably outperforms the classical baseline.

```mermaid
flowchart TD
    BASELINE["Run Classical<br/>Baseline Simulation"] --> AI_SIM["Run AI-Optimized<br/>Simulation"]
    AI_SIM --> COMPARE["Compare Metrics:<br/>Latency, Throughput, Loss"]
    COMPARE --> IMPROVED{"AI ≥ 15% better<br/>on latency?"}
    IMPROVED -->|"Yes"| DONE["✅ Convergence<br/>Achieved"]
    IMPROVED -->|"No"| TUNE["Tune:<br/>• RL reward weights<br/>• Prediction threshold<br/>• Anomaly sensitivity"]
    TUNE --> AI_SIM

    style DONE fill:#2ed573,color:#000
    style TUNE fill:#e94560,color:#fff
```

---

## 5. Failure Handling Strategy

### 5.1 Failure Taxonomy

```mermaid
flowchart TD
    FAILURE["⚠️ Failure Detected"] --> TYPE{"Failure<br/>Type?"}

    TYPE -->|"Agent Crash"| RESTART["Restart Agent<br/>(max 3 attempts)"]
    TYPE -->|"Invalid Output"| RETRY["Refine Params<br/>& Retry"]
    TYPE -->|"Model Divergence"| RETRAIN_F["Force Retrain<br/>from Checkpoint"]
    TYPE -->|"No Route Found"| FALLBACK_F["Cascade Fallback:<br/>RL → Dijkstra → BFS"]
    TYPE -->|"Data Corruption"| REJECT["Reject Input<br/>+ Descriptive Error"]
    TYPE -->|"Timeout"| TIMEOUT["Kill + Fallback<br/>to Cached Result"]

    RESTART --> RECOVERED{"Recovered?"}
    RECOVERED -->|"Yes"| CONTINUE_F["Continue Pipeline"]
    RECOVERED -->|"No"| DEGRADE["Graceful Degradation:<br/>Skip Agent, Use Default"]

    RETRY --> MAX{"Retry<br/>Count < 3?"}
    MAX -->|"Yes"| AGENT_RETRY["Re-execute Agent"]
    MAX -->|"No"| DEGRADE

    style FAILURE fill:#ff6b6b,color:#fff
    style DEGRADE fill:#ffa502,color:#000
    style CONTINUE_F fill:#2ed573,color:#000
```

### 5.2 Fallback Strategy Table

| Failure Scenario                    | Primary Action                 | Fallback Action                       | Last Resort                     |
| ----------------------------------- | ------------------------------ | ------------------------------------- | ------------------------------- |
| RL model not trained                | Log warning                    | Use weighted Dijkstra                 | Use unweighted BFS              |
| Congestion prediction fails         | Retry with reduced features    | Use threshold-based heuristic (>85%)  | Disable prediction, route normally |
| Anomaly detection crash             | Restart detector               | Use simple z-score threshold          | Disable detection, log all traffic |
| Simulation timeout (>5 min)         | Reduce tick count              | Return partial results                | Return cached baseline results  |
| Data ingestion parse error          | Try alternate parser           | Skip malformed rows + warning         | Reject file with error details  |
| Topology generation invalid         | Retry with higher connectivity | Use default 20-node random graph      | Raise `TopologyError`           |

### 5.3 Circuit Breaker Pattern

Each agent has a circuit breaker that prevents cascading failures:

```
CLOSED (normal) → on 3 consecutive failures → OPEN (reject all tasks for 30s)
OPEN → after 30s → HALF-OPEN (allow 1 trial task)
HALF-OPEN → if trial succeeds → CLOSED | if trial fails → OPEN
```

---

## 6. Optimization Steps

### 6.1 Route Optimization Pipeline

```mermaid
flowchart LR
    subgraph Step1["1. Static Optimization"]
        D["Dijkstra<br/>Shortest Path"]
    end

    subgraph Step2["2. Multi-Path"]
        E["ECMP<br/>Load Balancing"]
    end

    subgraph Step3["3. Predictive"]
        P["Congestion-Aware<br/>Weight Adjustment"]
    end

    subgraph Step4["4. Adaptive"]
        RL_OPT["RL Agent<br/>Learned Policy"]
    end

    subgraph Step5["5. Reactive"]
        REROUTE["Anomaly-Triggered<br/>Auto-Reroute"]
    end

    Step1 -->|"Baseline"| Step2
    Step2 -->|"+ Load Balance"| Step3
    Step3 -->|"+ Prediction"| Step4
    Step4 -->|"+ Anomaly Response"| Step5

    style Step1 fill:#1a1a2e,color:#eee
    style Step2 fill:#16213e,color:#eee
    style Step3 fill:#0f3460,color:#eee
    style Step4 fill:#e94560,color:#fff
    style Step5 fill:#2ed573,color:#000
```

### 6.2 Performance Optimization Techniques

| Level              | Technique                               | Impact                               |
| ------------------ | --------------------------------------- | ------------------------------------ |
| **Algorithm**      | Fibonacci heap Dijkstra                 | O(V log V + E) instead of O(V²)     |
| **Caching**        | LRU cache for repeated route queries    | Avoid recomputation on stable topology |
| **Batch Inference** | Batch ML predictions (100 links/call)  | 50ms per batch vs 10ms × 100 sequential |
| **Lazy Loading**   | Load ML models only on first use        | CLI startup ≤1s                      |
| **Pruning**        | Skip down links before routing          | Reduce graph size for algorithms     |
| **Parallel**       | Train prediction + anomaly models in parallel | 40% reduction in training time |

---

## 7. Scalability Architecture

### 7.1 Scaling Dimensions

```mermaid
graph TD
    subgraph Vertical["Vertical Scaling (V1)"]
        V1["Single-process<br/>Python application"]
        V2["NetworkX graphs<br/>≤5,000 edges"]
        V3["CPU-based ML<br/>training & inference"]
    end

    subgraph Horizontal["Horizontal Scaling (V2+)"]
        H1["Multi-process<br/>simulation workers"]
        H2["graph-tool / igraph<br/>for 100K+ edges"]
        H3["GPU-accelerated<br/>training (CUDA)"]
        H4["Distributed simulation<br/>(Ray / Dask)"]
        H5["Streaming ingestion<br/>(Kafka / ZMQ)"]
    end

    Vertical -->|"Future Evolution"| Horizontal

    style Vertical fill:#16213e,color:#eee
    style Horizontal fill:#0f3460,color:#eee
```

### 7.2 Scaling Strategy by Component

| Component          | V1 (Current)               | V2 (Planned)                            | V3 (Future)                        |
| ------------------ | -------------------------- | --------------------------------------- | ---------------------------------- |
| **Topology**       | NetworkX, ≤5K edges        | igraph/graph-tool, ≤100K edges          | Distributed graph DB (JanusGraph)  |
| **Routing**        | Single-thread algorithms   | Multi-process k-shortest-paths          | GPU-accelerated GNN routing        |
| **ML Training**    | CPU, single-process        | GPU via CUDA, parallel hyperparameter search | Distributed training (PyTorch DDP) |
| **ML Inference**   | CPU, synchronous           | Batch inference, ONNX Runtime           | Edge-deployed models (TensorRT)    |
| **Simulation**     | Single-process, sequential | Multi-process workers (1 per topology)  | Ray-based distributed simulation   |
| **Data Ingestion** | File-based, batch          | Streaming (Kafka consumer)              | Real-time pipeline (Flink)         |
| **Agents**         | In-process function calls  | Async with message queue                | Microservices with gRPC            |

### 7.3 Agent Concurrency Model

```mermaid
flowchart TD
    subgraph V1["V1: Sequential + Selective Parallel"]
        ORC_V1["Orchestrator<br/>(main thread)"]
        ORC_V1 --> SEQ["Sequential Tasks<br/>(dependent agents)"]
        ORC_V1 --> PAR["Parallel Tasks<br/>(independent agents)<br/>via ThreadPoolExecutor"]
    end

    subgraph V2["V2: Async Agent Pool"]
        ORC_V2["Orchestrator<br/>(asyncio event loop)"]
        ORC_V2 --> POOL["Agent Pool<br/>(ProcessPoolExecutor)"]
        POOL --> A1["Topology Worker"]
        POOL --> A2["Routing Worker"]
        POOL --> A3["ML Worker"]
        POOL --> A4["Simulation Worker"]
    end

    subgraph V3["V3: Distributed Agents"]
        ORC_V3["Orchestrator<br/>(Message Broker)"]
        ORC_V3 --> Q["Task Queue<br/>(Redis / RabbitMQ)"]
        Q --> W1["Worker Node 1"]
        Q --> W2["Worker Node 2"]
        Q --> W3["Worker Node N"]
    end

    V1 -->|"Scale Up"| V2
    V2 -->|"Scale Out"| V3
```

---

## 8. Agent Communication Protocol

### 8.1 Message Format

All inter-agent communication uses a standardized message envelope:

```python
@dataclass
class AgentMessage:
    task_id: str              # Unique task identifier (UUID)
    source_agent: str         # Sender agent name
    target_agent: str         # Receiver agent name
    task_type: str            # e.g., "compute_route", "predict_congestion"
    priority: int             # 0 (low) to 10 (critical)
    payload: dict             # Task-specific data
    metadata: dict            # Timestamps, retry count, parent task ID
    status: str               # "pending" | "in_progress" | "completed" | "failed"
```

### 8.2 Communication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant T as Topology Agent
    participant R as Routing Agent
    participant V as Validation Agent

    U->>O: "Compute route A→Z on fat-tree"
    O->>O: Decompose: [build topology, compute route]

    O->>T: AgentMessage(task="generate", payload={type: "fat-tree", k: 4})
    T->>T: Generate topology
    T->>O: AgentMessage(status="completed", payload={topology: ...})

    O->>V: AgentMessage(task="validate_topology", payload={topology: ...})
    V->>O: AgentMessage(status="completed", payload={valid: true})

    O->>R: AgentMessage(task="compute_route", payload={topo, src: "A", dst: "Z"})
    R->>R: Run Dijkstra
    R->>O: AgentMessage(status="completed", payload={route_metrics: ...})

    O->>V: AgentMessage(task="validate_route", payload={route: ...})
    V->>O: AgentMessage(status="completed", payload={valid: true})

    O->>U: Final Result: path=[A, B, D, Z], latency=15ms
```

---

## 9. Monitoring & Observability

### 9.1 Agent Health Dashboard (Conceptual)

| Metric                    | Source                | Threshold                | Alert On                    |
| ------------------------- | --------------------- | ------------------------ | --------------------------- |
| Agent response time       | Each agent            | ≤100ms (routing), ≤5s (training) | 3× consecutive threshold breach |
| Task success rate         | Orchestrator          | ≥95% per agent           | Drops below 90%             |
| Validation pass rate      | Validation Agent      | ≥90% first-attempt       | Drops below 80%             |
| Model accuracy drift      | Prediction/Anomaly    | Precision ≥80%           | Drops below 75%             |
| Memory usage              | All agents            | ≤2GB per agent           | Exceeds 3GB                 |
| Queue depth               | Orchestrator          | ≤50 pending tasks        | Exceeds 100                 |

### 9.2 Structured Logging

Every agent logs using `structlog` with:
```json
{
  "timestamp": "2026-06-11T14:30:00Z",
  "agent": "routing_agent",
  "task_id": "abc-123",
  "event": "route_computed",
  "algorithm": "dijkstra",
  "source": "A",
  "destination": "Z",
  "latency_ms": 15.2,
  "hops": 3,
  "duration_ms": 4.7
}
```

---

## 10. Summary: Agent Roster

| Agent              | Icon | Primary Input                | Primary Output               | Feedback Trigger                     |
| ------------------ | ---- | ---------------------------- | ---------------------------- | ------------------------------------ |
| **Orchestrator**   | 🎯  | User commands, agent results | Task assignments, final results | Validation failure, timeout          |
| **Topology**       | 🏗️  | Generation params / raw data | `Topology` object            | Invalid structure, disconnected graph |
| **Data Ingestion** | 📥  | Raw files (CSV/JSON/pcap)    | `Topology` / `TrafficMatrix` | Parse errors, missing fields         |
| **Routing**        | 🛤️  | Topology + src/dst + algo    | `RouteMetrics`               | Invalid path, no route found         |
| **Prediction**     | 🔮  | Topology + traffic history   | Congestion probabilities     | Precision < 80%, drift detected      |
| **Anomaly**        | 🛡️  | Traffic data                 | Anomaly scores + types       | Detection rate < 90%, false positives |
| **Simulation**     | ⚙️  | Topology + config + algo     | `MetricsCollectionResult`    | Timeout, invalid metrics             |
| **Validation**     | 📊  | Any agent output             | Pass/Fail + feedback         | *(Always runs — never skipped)*      |

---

*End of Multi-Agent AI System Architecture*
