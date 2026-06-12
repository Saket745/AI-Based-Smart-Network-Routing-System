# Production Deployment Guidelines — nroute

This document outlines instructions for containerizing the `nroute` CLI and deploying it to production environments, Docker containers, and Kubernetes clusters.

---

## 1. Docker Build Instructions

To build a lightweight, multi-staged production Docker image of the `nroute` CLI:

```bash
docker build -t nroute:latest .
```

### Run Commands Inside Docker
Run any nroute CLI subcommand inside the container, passing arguments directly:

```bash
# Get help
docker run --rm nroute:latest --help

# Run a simulation using local data folders
docker run --rm \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/output:/app/output" \
  nroute:latest simulate run -t data/sample_topology.json -a dijkstra -d 50 -o output/sim_results.json
```

---

## 2. Docker Compose Integration

The repository includes a sample `docker-compose.yml` to orchestrate multi-container execution (e.g. executing simulations and training machine learning models in parallel).

To build images and spin up compose services:

```bash
docker-compose up --build
```

---

## 3. Kubernetes Orchestration

For cloud-scale batch simulation runs and model evaluations, schedule container execution via Kubernetes Jobs.

Apply the job template:

```bash
kubectl apply -f k8s/nroute-deployment.yaml
```

### Resource Allocation Recommendations
* **Simulations without ML**: Requires minimal CPU and memory (`1 vCPU` and `1-2Gi` memory).
* **AI Router / LSTM congestion models**: Requires at least `2 vCPUs` and `4Gi` memory to prevent OOM errors during neural network backpropagation or Gym/Gymnasium RL rollouts.
