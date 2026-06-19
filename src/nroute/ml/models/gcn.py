"""Graph Convolutional Network (GCN) implemented in pure PyTorch."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F  # noqa: N812


class GCNConv(nn.Module):
    """
    Symmetric normalized spectral Graph Convolution Layer using raw PyTorch scatter/index_add.
    """

    def __init__(self, in_features: int, out_features: int) -> None:
        super().__init__()
        self.linear = nn.Linear(in_features, out_features, bias=False)
        self.bias = nn.Parameter(torch.zeros(out_features))

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Node features of shape [N, in_features]
            edge_index: Adjacency list (COO layout) of shape [2, E]
        """
        num_nodes = x.size(0)

        # 1. Add self-loops (A_tilde = A + I)
        self_loops = torch.stack(
            [
                torch.arange(num_nodes, device=edge_index.device),
                torch.arange(num_nodes, device=edge_index.device),
            ],
            dim=0,
        )
        edge_index_tilde = torch.cat([edge_index, self_loops], dim=1)

        # 2. Compute symmetric normalization coefficients
        row, col = edge_index_tilde[0], edge_index_tilde[1]

        deg = torch.zeros(num_nodes, device=edge_index.device)
        deg.index_add_(0, col, torch.ones_like(col, dtype=torch.float32))

        deg_inv_sqrt = torch.pow(deg, -0.5)
        deg_inv_sqrt[torch.isinf(deg_inv_sqrt)] = 0.0

        # Normalization coefficient for each edge: 1 / sqrt(deg_i * deg_j)
        norm = deg_inv_sqrt[row] * deg_inv_sqrt[col]

        # 3. Project features
        h = self.linear(x)

        # 4. Message passing
        msg = h[row] * norm.unsqueeze(1)
        out = torch.zeros(num_nodes, h.size(1), device=edge_index.device)
        out.index_add_(0, col, msg)

        # 5. Add bias
        return out + self.bias


class GCNModel(nn.Module):
    """
    Multi-task GCN model for node embedding, link congestion, and latency predictions.
    """

    preferred_extension = ".pt"

    def __init__(
        self,
        node_in_dim: int,
        edge_in_dim: int,
        hidden_dim: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.model_type = "gcn"

        # GCN layers
        self.convs = nn.ModuleList()
        self.convs.append(GCNConv(node_in_dim, hidden_dim))
        for _ in range(num_layers - 1):
            self.convs.append(GCNConv(hidden_dim, hidden_dim))

        self.dropout = dropout

        # Multi-task edge prediction heads
        # Input to edge head: concatenation of source node embedding, destination node embedding, and raw edge features
        edge_head_in_dim = hidden_dim * 2 + edge_in_dim

        # Congestion classifier (output: probability of congestion)
        self.congestion_head = nn.Sequential(
            nn.Linear(edge_head_in_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

        # Latency regressor (output: estimated latency)
        self.latency_head = nn.Sequential(
            nn.Linear(edge_head_in_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        edge_features: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            node_features: Shape [N, node_in_dim]
            edge_index: Shape [2, E]
            edge_features: Shape [E, edge_in_dim]

        Returns:
            Tuple of (congestion_logits, latency_predictions)
        """
        # 1. Compute node embeddings via GCN layers
        h = node_features
        for i, conv in enumerate(self.convs):
            h = conv(h, edge_index)
            if i < len(self.convs) - 1:
                h = F.relu(h)
                h = F.dropout(h, p=self.dropout, training=self.training)

        # 2. Build edge representations
        if edge_index.size(1) > 0:
            src_idx, dst_idx = edge_index[0], edge_index[1]
            src_embeds = h[src_idx]
            dst_embeds = h[dst_idx]
            edge_embeds = torch.cat([src_embeds, dst_embeds, edge_features], dim=-1)

            # 3. Compute multi-task outputs
            congestion_logits = self.congestion_head(edge_embeds).squeeze(-1)
            latency_pred = self.latency_head(edge_embeds).squeeze(-1)
        else:
            congestion_logits = torch.empty((0,), device=node_features.device)
            latency_pred = torch.empty((0,), device=node_features.device)

        return congestion_logits, latency_pred

    def save(self, path: str) -> None:
        """Save the model state dict to a file."""
        torch.save(self.state_dict(), path)

    def load(self, path: str) -> None:
        """Load the model state dict from a file."""
        self.load_state_dict(torch.load(path, map_location="cpu"))
