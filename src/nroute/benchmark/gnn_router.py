"""GNN-weighted Dijkstra router for Phase-2 structural generalization benchmarking."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import networkx as nx
import torch

from nroute.ml.features.extractor import DefaultGraphFeatureExtractor
from nroute.routing.base import BaseRouter

if TYPE_CHECKING:
    from nroute.core.topology import Topology
    from nroute.ml.models.gcn import GCNModel
    from nroute.ml.models.graphsage import GraphSAGEModel


class GNNRouter(BaseRouter):
    """
    GNN-derived edge weight router.
    Evaluates GCN or GraphSAGE model over topology graph to predict link congestion/latency,
    and routes flows using Dijkstra path solving over GNN-weighted edges.
    """

    def __init__(
        self,
        model: GCNModel | GraphSAGEModel,
        alpha: float = 5.0,
        use_latency_head: bool = False,
    ) -> None:
        super().__init__()
        self.model = model
        self.model.eval()
        self.alpha = alpha
        self.use_latency_head = use_latency_head
        self.extractor = DefaultGraphFeatureExtractor(use_pytorch=True)

        # Stage timings in nanoseconds for the last query
        self.last_extract_ns: float = 0.0
        self.last_infer_ns: float = 0.0
        self.last_solve_ns: float = 0.0
        self.last_total_ns: float = 0.0

    def compute_edge_weights(self, topology: Topology) -> dict[tuple[str, str], float]:
        """
        Extract graph tensors, execute GNN forward pass, and compute edge weights.
        """
        # 1. Feature extraction
        t0 = time.perf_counter_ns()
        bundle = self.extractor.extract_features(topology)
        t1 = time.perf_counter_ns()

        # 2. Model Inference
        with torch.no_grad():
            cong_logits, lat_preds = self.model(
                bundle.node_features,
                bundle.edge_index,
                bundle.edge_features,
            )
            cong_probs = torch.sigmoid(cong_logits).cpu().numpy()
            lat_vals = lat_preds.cpu().numpy()
        t2 = time.perf_counter_ns()

        self.last_extract_ns = float(t1 - t0)
        self.last_infer_ns = float(t2 - t1)

        # 3. Build edge weight map
        edge_weights: dict[tuple[str, str], float] = {}
        idx_to_node = bundle.idx_to_node
        e_idx = bundle.edge_index
        edge_index_np: Any = e_idx.cpu().numpy() if hasattr(e_idx, "cpu") else e_idx

        num_edges = int(edge_index_np.shape[1])
        for i in range(num_edges):
            u = idx_to_node[int(edge_index_np[0, i])]
            v = idx_to_node[int(edge_index_np[1, i])]
            attrs = topology.get_edge(u, v)
            base_latency = float(attrs.get("latency", 5.0))

            if self.use_latency_head:
                w = float(max(0.1, lat_vals[i]))
            else:
                prob = float(cong_probs[i])
                w = base_latency * (1.0 + self.alpha * prob)

            edge_weights[(u, v)] = w

        return edge_weights

    def compute_path(
        self,
        topology: Topology,
        source: str,
        destination: str,
        weight: Any = None,
        **kwargs: Any,
    ) -> list[str]:
        """Compute path using GNN-predicted edge costs."""
        t_start = time.perf_counter_ns()

        edge_weights = self.compute_edge_weights(topology)

        # 3. Path solving
        t_solve_start = time.perf_counter_ns()

        def gnn_weight_func(u: str, v: str, d: dict[str, Any]) -> float:
            if d.get("status", "up") == "down":
                return float("inf")
            return edge_weights.get((u, v), float(d.get("latency", 5.0)))

        try:
            path = list(
                nx.shortest_path(
                    topology.graph,
                    source=source,
                    target=destination,
                    weight=gnn_weight_func,
                )
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            path = []

        t_end = time.perf_counter_ns()
        self.last_solve_ns = float(t_end - t_solve_start)
        self.last_total_ns = float(t_end - t_start)

        return path
