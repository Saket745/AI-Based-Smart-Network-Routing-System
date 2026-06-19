# GRAPHSAGE_SPEC.md

## 1. Overview
GraphSAGE is an inductive GNN architecture that learns aggregate functions over local neighborhoods. Rather than relying on the full graph Laplacian, it generalizes easily to unseen topologies at inference time.

---

## 2. GraphSAGE Formulation
The update rule for a node representation $h_i^{(l)}$ in GraphSAGE is:

$$h_{\mathcal{N}(i)}^{(l+1)} = \text{AGGREGATE}\left( \{ h_j^{(l)}, \forall j \in \mathcal{N}(i) \} \right)$$

$$h_i^{(l+1)} = \sigma \left( W^{(l)} \cdot \left[ h_i^{(l)} \,||\, h_{\mathcal{N}(i)}^{(l+1)} \right] \right)$$

Where:
* $\text{AGGREGATE}$ is a pooling function (typically `MEAN` or `MAX` pooling).
* $[ \cdot \,||\, \cdot ]$ represents vector concatenation.
* $W^{(l)}$ is a learned transformation matrix.
* $\sigma$ is the non-linear activation (typically `ReLU`).

---

## 3. Pure PyTorch Implementation Design
We implement the SAGE convolution layer using scatter operations:

```python
class SAGEConv(nn.Module):
    def __init__(self, in_features: int, out_features: int) -> None:
        super().__init__()
        self.lin_self = nn.Linear(in_features, out_features, bias=False)
        self.lin_neigh = nn.Linear(in_features, out_features, bias=False)
        self.bias = nn.Parameter(torch.zeros(out_features))

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        # 1. Compute mean of target node neighbors' features
        # 2. Map self features via lin_self, neighbor features via lin_neigh
        # 3. Sum the outputs and apply bias and non-linearity
```

---

## 4. Multi-Task Heads
Similar to GCN, node embeddings $H$ are pooled or concatenated to feed the edge classification and path regression heads.
