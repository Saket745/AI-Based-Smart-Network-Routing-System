# FEATURE_ENGINEERING_SPEC.md

## 1. Node Features (Feature Vector: `[N, F_N]`)
The GNN consumes topological and dynamic node metrics:

| Feature Name | Type | Description / Calculation |
| :--- | :--- | :--- |
| **Degree** | `float` | Number of neighbor links (normalized by max degree). |
| **Betweenness Centrality** | `float` | Fraction of all shortest paths passing through the node. |
| **Closeness Centrality** | `float` | Reciprocal of the sum of the shortest path distances from a given node to all other nodes. |
| **Queue Length** | `float` | Current queue size at the node's packet buffer. |
| **Packet Load** | `float` | Total volume of packets currently processed at the node. |
| **Congestion Score** | `float` | Dynamic ratio of queue length to capacity. |

---

## 2. Edge Features (Feature Vector: `[E, F_E]`)
Edges describe physical link parameters and active telemetry:

| Feature Name | Type | Description / Calculation |
| :--- | :--- | :--- |
| **Bandwidth** | `float` | Link capacity in Mbps (log-scaled or normalized). |
| **Latency** | `float` | Current edge delay in milliseconds. |
| **Utilization** | `float` | Dynamic utilization ratio (current flow volume / bandwidth). |
| **Packet Loss** | `float` | Probabilistic loss rate on the link. |
| **Reliability** | `float` | Exponential moving average of link uptime. |
| **Failure Frequency** | `float` | Count of failure events injected on this edge. |

---

## 3. Scaling & Normalization
* Centrality values are calculated using **NetworkX** and scaled to the range `[0.0, 1.0]`.
* Dynamic metrics (utilization, loss) are kept within their natural bounds `[0.0, 1.0]`.
* Numerical values like bandwidth and queue size are normalized using min-max scaling or z-score standardization before conversion to tensors.
