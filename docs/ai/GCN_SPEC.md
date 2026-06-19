# GCN_SPEC.md

## 1. Overview
The Graph Convolutional Network (GCN) aggregates local neighborhood information using a normalized spectral formulation. Since we are using pure PyTorch, we implement this aggregation without PyTorch Geometric.

---

## 2. GCN Formulation
For a node $i$, the GCN layer updates its representation $h_i^{(l)}$ as follows:

$$h_i^{(l+1)} = \sigma \left( \sum_{j \in \mathcal{N}(i) \cup \{i\}} \frac{1}{\sqrt{\tilde{D}_{ii}\tilde{D}_{jj}}} h_j^{(l)} W^{(l)} \right)$$

Where:
* $\mathcal{N}(i)$ is the set of neighbors of node $i$.
* $\tilde{A} = A + I_N$ is the adjacency matrix with added self-loops.
* $\tilde{D}$ is the diagonal degree matrix of $\tilde{A}$.
* $W^{(l)}$ is the learned weight matrix of layer $l$.
* $\sigma$ is an activation function (typically `ReLU`).

---

## 3. Pure PyTorch Implementation Design
We implement GCN aggregation via sparse or dense matrix multiplication in PyTorch:

```python
class GCNConv(nn.Module):
    def __init__(self, in_features: int, out_features: int) -> None:
        super().__init__()
        self.linear = nn.Linear(in_features, out_features, bias=False)
        self.bias = nn.Parameter(torch.zeros(out_features))

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        # 1. Add self loops to edge_index
        # 2. Compute symmetric degree normalization coefficients
        # 3. Perform message passing using scatter operations or sparse multiplications
        # 4. Apply linear mapping and bias
```

---

## 4. Multi-Task Heads
* **Node Embedding**: Multi-layer GCN outputs a node matrix $H \in \mathbb{R}^{N \times H_{\text{dim}}}$.
* **Link Congestion Prediction**: For each edge $(u, v)$, GCN concatenates or computes dot product of node embeddings $h_u$ and $h_v$, passes it through a 2-layer MLP to output a congestion score:
  $$\hat{y}_{u \to v} = \text{MLP}([h_u || h_v || e_{u \to v}])$$
