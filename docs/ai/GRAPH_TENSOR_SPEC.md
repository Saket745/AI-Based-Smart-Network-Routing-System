# GRAPH_TENSOR_SPEC.md

## 1. Overview
The Graph Representation Layer converts a `Topology` graph object into tensor arrays that PyTorch models can ingest.

---

## 2. GraphTensorBundle Specification
Every GNN-compatible topology snapshot must be packed into a `GraphTensorBundle`:

```python
class GraphTensorBundle:
    node_features: torch.Tensor  # Shape: [N, F_N]
    edge_index: torch.Tensor     # Shape: [2, E] (COO layout)
    edge_features: torch.Tensor    # Shape: [E, F_E]
    node_to_idx: dict[str, int]  # Mapping from node string ID to index
    idx_to_node: list[str]       # Mapping from index to node string ID
```

### COO Edge Index Layout
Edges are represented in COO (Coordinate) format. For a directed link from node A (index 0) to node B (index 1), `edge_index` contains `[0, 1]`.

---

## 3. PyTorch Batching & Compatibility
For batched training, multiple `GraphTensorBundle` objects are combined:
* **Disjoint Union**: Adjacency matrices are placed diagonally. The `edge_index` offsets are incremented by the cumulative node count of previous graphs in the batch.
* **Feature Concatenation**: Node features are concatenated along the first dimension.

This ensures standard graph mini-batching works efficiently.
