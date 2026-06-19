"""GNN Model baseline architectures."""

from nroute.ml.models.gcn import GCNConv, GCNModel
from nroute.ml.models.graphsage import GraphSAGEModel, SAGEConv

__all__ = ["GCNConv", "GCNModel", "GraphSAGEModel", "SAGEConv"]
