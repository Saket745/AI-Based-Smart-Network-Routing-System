# Development Roadmap — AI-Based Smart Network Routing System

This document outlines the strategic milestones and features planned for the **nroute** library and simulation engine.

---

## 🗺️ Vision
To provide a production-grade, highly extensible framework that bridges classical networking routing algorithms with advanced predictive ML models and reinforcement learning agents for adaptive path optimization.

---

## 📍 Milestones & Phases

### Phase 1: Core Scaffolding & Classical Routing (Current)
* [x] Establish directory governance, CI pipelines, and pre-commit commit validation.
* [x] Implement core graph topology engines (e.g. fat-tree, grid, random topologies).
* [x] Implement classical routing algorithms (Dijkstra, ECMP, Bellman-Ford).
* [x] Implement basic discrete-event simulation engine with traffic matrix ingestion.
* [x] Achieve >80% code coverage on unit tests.

### Phase 2: Anomaly Detection & Congestion Prediction (Q3 2026)
* [x] Integrate data ingestion engines (PCAP parsing, SNMP simulation, NetFlow CSV records).
* [x] Develop an anomaly detection module (Isolation Forest, Autoencoders) to identify link failure anomalies, black holes, and DDoS patterns.
* [x] Implement a congestion prediction module using time-series forecasting (XGBoost, LSTM) to predict link traffic saturation 5-15 minutes in advance.
* [x] Create dynamic edge weight calculators that adjust graph link weights reactively based on predicted congestion.

### Phase 3: Reinforcement Learning & AI-Driven Routing (Q4 2026)
* [x] Develop a Gym/Gymnasium-compatible environment for routing optimization.
* [x] Implement Reinforcement Learning (RL) routing agents utilizing Proximal Policy Optimization (PPO) and Deep Q-Networks (DQN).
* [x] Build multi-agent routing simulations where individual nodes negotiate traffic patterns.
* [x] Compare RL-based routing efficiency against classical OSPF/ECMP under dynamic link failure scenarios.

### Phase 4: Productionization & Extensibility (Q1 2027)
* [ ] Add real-time interactive visualization console (Plotext/Dash) to watch packets flow through the network graph.
* [ ] Package and publish **nroute** to PyPI.
* [ ] Build out production deployment guidelines, CLI docker images, and cloud integration templates.
* [ ] Establish open APIs for adding custom neural networks and third-party routing strategies.

---

## 📈 Long-Term Research Agenda
* **Graph Neural Networks (GNNs):** Deep learning on graph topologies to generalise routing policies across completely unseen topologies.
* **Distributed Routing Protocols:** Adapting central routing controllers into a distributed consensus-based routing architecture.
