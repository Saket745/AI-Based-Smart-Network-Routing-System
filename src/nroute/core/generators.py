"""Generators for synthetic topologies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import networkx as nx

if TYPE_CHECKING:
    import numpy as np

from nroute.core.topology import Topology
from nroute.exceptions import TopologyError
from nroute.utils.random import get_rng


class TopologyGenerator:
    """
    Generator class providing static methods to construct standard network topologies.
    """

    @staticmethod
    def _assign_random_edge_attrs(graph: nx.DiGraph, rng: Any, **default_attrs: Any) -> None:
        """Helper to assign randomized link attributes to a Graph's edges."""
        bw_arg = default_attrs.get("bandwidth")
        lat_arg = default_attrs.get("latency")
        jit_arg = default_attrs.get("jitter")
        loss_arg = default_attrs.get("packet_loss")
        util_val = default_attrs.get("utilization", 0.0)
        status_val = default_attrs.get("status", "up")
        weight_arg = default_attrs.get("weight")

        bw_choices = (100.0, 1000.0, 10000.0)
        loss_choices = (0.0, 0.001, 0.005, 0.01, 0.02)

        # Pre-filter extra custom attributes once outside the edge traversal loop
        extra_attrs = {
            k: v
            for k, v in default_attrs.items()
            if k
            not in {
                "bandwidth",
                "latency",
                "jitter",
                "packet_loss",
                "utilization",
                "weight",
                "status",
            }
        }

        # Direct adjacency dictionary access bypassing EdgeView descriptor overhead
        adj = getattr(graph, "_adj", graph.edges)
        has_adj = hasattr(graph, "_adj")

        for src, dst in graph.edges:
            bandwidth = float(rng.choice(bw_choices)) if bw_arg is None else bw_arg
            latency = float(round(rng.uniform(1.0, 50.0), 1)) if lat_arg is None else lat_arg
            jitter = float(round(rng.uniform(0.1, 5.0), 2)) if jit_arg is None else jit_arg
            packet_loss = float(rng.choice(loss_choices)) if loss_arg is None else loss_arg
            weight = latency if weight_arg is None else weight_arg

            edge_attrs = {
                "bandwidth": bandwidth,
                "latency": latency,
                "jitter": jitter,
                "packet_loss": packet_loss,
                "utilization": util_val,
                "weight": weight,
                "status": status_val,
            }
            if extra_attrs:
                edge_attrs.update(extra_attrs)

            if has_adj:
                adj[src][dst].update(edge_attrs)
            else:
                adj[src, dst].update(edge_attrs)

    @staticmethod
    def _assign_default_node_attrs(
        graph: nx.DiGraph, node_type: str, rng: Any, **default_attrs: Any
    ) -> None:
        """Helper to assign node attributes to all nodes in the Graph."""
        cap_arg = default_attrs.get("capacity")
        if cap_arg is None:
            if node_type == "host":
                capacity_val = 1000.0
            elif node_type == "switch":
                capacity_val = 10000.0
            elif node_type == "router":
                capacity_val = 40000.0
            else:
                capacity_val = 10000.0
        else:
            capacity_val = cap_arg

        status_val = default_attrs.get("status", "up")
        location_val = default_attrs.get("location")

        # Pre-filter extra custom attributes once outside the node iteration loop
        extra_attrs = {
            k: v
            for k, v in default_attrs.items()
            if k not in {"type", "capacity", "status", "location"}
        }

        # Direct node dictionary access bypassing NodeView descriptor overhead
        node_dict = getattr(graph, "_node", graph.nodes)

        node_attrs = {
            "type": node_type,
            "capacity": capacity_val,
            "status": status_val,
            "location": location_val,
        }
        if extra_attrs:
            node_attrs.update(extra_attrs)

        for node in graph.nodes:
            node_dict[node].update(node_attrs)

    @staticmethod
    def _add_fat_tree_core_layer(graph: nx.DiGraph, k: int) -> list[str]:
        """Add core switches to the Fat-Tree graph."""
        num_core = (k // 2) ** 2
        core_nodes = []
        for i in range(num_core):
            core_id = f"core_{i}"
            graph.add_node(core_id, type="switch", capacity=40000.0, status="up", location="core")
            core_nodes.append(core_id)
        return core_nodes

    @staticmethod
    def _add_pod_agg_switches(graph: nx.DiGraph, pod_idx: int, num_agg: int) -> list[str]:
        """Add Aggregation Switches for a pod."""
        agg_nodes = []
        for agg in range(num_agg):
            agg_id = f"pod_{pod_idx}_agg_{agg}"
            graph.add_node(
                agg_id, type="switch", capacity=10000.0, status="up", location=f"pod_{pod_idx}"
            )
            agg_nodes.append(agg_id)
        return agg_nodes

    @staticmethod
    def _add_pod_edge_switches_and_hosts(
        graph: nx.DiGraph, pod_idx: int, num_edge: int, num_hosts: int, **default_attrs: Any
    ) -> list[str]:
        """Add Edge Switches and Hosts for a pod, and connect them."""
        edge_nodes = []
        host_bw = default_attrs.get("host_bandwidth", 1000.0)
        host_lat = default_attrs.get("host_latency", 0.5)

        for edge in range(num_edge):
            edge_id = f"pod_{pod_idx}_edge_{edge}"
            graph.add_node(
                edge_id, type="switch", capacity=10000.0, status="up", location=f"pod_{pod_idx}"
            )
            edge_nodes.append(edge_id)

            for host in range(num_hosts):
                host_id = f"pod_{pod_idx}_host_{edge}_{host}"
                graph.add_node(
                    host_id, type="host", capacity=1000.0, status="up", location=f"pod_{pod_idx}"
                )

                # Connect Host <--> Edge Switch (bidirectional)
                graph.add_edge(
                    host_id,
                    edge_id,
                    bandwidth=host_bw,
                    latency=host_lat,
                    jitter=0.01,
                    packet_loss=0.0,
                    utilization=0.0,
                    status="up",
                    weight=host_lat,
                )
                graph.add_edge(
                    edge_id,
                    host_id,
                    bandwidth=host_bw,
                    latency=host_lat,
                    jitter=0.01,
                    packet_loss=0.0,
                    utilization=0.0,
                    status="up",
                    weight=host_lat,
                )
        return edge_nodes

    @staticmethod
    def _connect_edge_to_agg(
        graph: nx.DiGraph, edge_nodes: list[str], agg_nodes: list[str], **default_attrs: Any
    ) -> None:
        """Connect Edge and Aggregation switches inside a pod."""
        pod_bw = default_attrs.get("pod_bandwidth", 10000.0)
        pod_lat = default_attrs.get("pod_latency", 1.0)
        for edge_id in edge_nodes:
            for agg_id in agg_nodes:
                for u, v in [(edge_id, agg_id), (agg_id, edge_id)]:
                    graph.add_edge(
                        u,
                        v,
                        bandwidth=pod_bw,
                        latency=pod_lat,
                        jitter=0.05,
                        packet_loss=0.0,
                        utilization=0.0,
                        status="up",
                        weight=pod_lat,
                    )

    @staticmethod
    def _connect_agg_to_core(
        graph: nx.DiGraph,
        agg_nodes: list[str],
        core_nodes: list[str],
        stride: int,
        **default_attrs: Any,
    ) -> None:
        """Connect Aggregation switches to Core switches."""
        core_bw = default_attrs.get("core_bandwidth", 40000.0)
        core_lat = default_attrs.get("core_latency", 2.0)
        for j, agg_id in enumerate(agg_nodes):
            start_core_idx = j * stride
            for offset in range(stride):
                core_id = core_nodes[start_core_idx + offset]
                for u, v in [(agg_id, core_id), (core_id, agg_id)]:
                    graph.add_edge(
                        u,
                        v,
                        bandwidth=core_bw,
                        latency=core_lat,
                        jitter=0.1,
                        packet_loss=0.001,
                        utilization=0.0,
                        status="up",
                        weight=core_lat,
                    )

    @staticmethod
    def _add_fat_tree_pod(
        graph: nx.DiGraph, k: int, pod_idx: int, core_nodes: list[str], **default_attrs: Any
    ) -> None:
        """Add a single pod (switches and hosts) and its connections to the Fat-Tree graph."""
        num_agg_per_pod = k // 2
        num_edge_per_pod = k // 2
        num_hosts_per_edge = k // 2

        # 1. Add Aggregation Switches
        agg_nodes = TopologyGenerator._add_pod_agg_switches(graph, pod_idx, num_agg_per_pod)

        # 2. Add Edge Switches and Hosts
        edge_nodes = TopologyGenerator._add_pod_edge_switches_and_hosts(
            graph, pod_idx, num_edge_per_pod, num_hosts_per_edge, **default_attrs
        )

        # 3. Connect Edge <--> Aggregation Switches inside Pod
        TopologyGenerator._connect_edge_to_agg(graph, edge_nodes, agg_nodes, **default_attrs)

        # 4. Connect Aggregation <--> Core Switches
        stride = k // 2
        TopologyGenerator._connect_agg_to_core(
            graph, agg_nodes, core_nodes, stride, **default_attrs
        )

    @classmethod
    def random(
        cls, n_nodes: int, edge_prob: float, seed: int | None = None, **default_attrs: Any
    ) -> Topology:
        """
        Generate a random network topology using Erdős-Rényi model.

        Args:
            n_nodes: Total number of nodes.
            edge_prob: Probability of link creation between any pair of nodes.
            seed: Random seed for reproducibility.
            default_attrs: Optional override attributes for nodes/edges.
        """
        if n_nodes <= 0:
            raise TopologyError("Number of nodes must be positive.")
        if not (0.0 <= edge_prob <= 1.0):
            raise TopologyError("Edge probability must be between 0.0 and 1.0.")

        rng = get_rng(seed)

        # Generate undirected graph and convert to directed
        undirected = nx.erdos_renyi_graph(n_nodes, edge_prob, seed=seed)
        directed = nx.DiGraph(undirected)

        # Relabel nodes to strings
        mapping = {node: str(node) for node in directed.nodes}
        directed = cast("nx.DiGraph", nx.relabel_nodes(directed, mapping))

        cls._assign_default_node_attrs(directed, "router", rng, **default_attrs)
        cls._assign_random_edge_attrs(directed, rng, **default_attrs)

        return Topology(directed)

    @classmethod
    def scale_free(cls, n_nodes: int, seed: int | None = None, **default_attrs: Any) -> Topology:
        """
        Generate a scale-free network topology using Barabási-Albert model.

        Args:
            n_nodes: Total number of nodes.
            seed: Random seed for reproducibility.
            default_attrs: Optional override attributes.
        """
        if n_nodes < 3:
            raise TopologyError("Scale-free topologies require at least 3 nodes.")

        rng = get_rng(seed)

        # Generate Barabási-Albert graph (m=2 attachments per new node)
        undirected = nx.barabasi_albert_graph(n_nodes, m=2, seed=seed)
        directed = nx.DiGraph(undirected)

        # Relabel nodes to strings
        mapping = {node: str(node) for node in directed.nodes}
        directed = cast("nx.DiGraph", nx.relabel_nodes(directed, mapping))

        cls._assign_default_node_attrs(directed, "router", rng, **default_attrs)
        cls._assign_random_edge_attrs(directed, rng, **default_attrs)

        return Topology(directed)

    @classmethod
    def small_world(
        cls,
        n_nodes: int,
        k_neighbors: int = 4,
        rewire_prob: float = 0.1,
        seed: int | None = None,
        **default_attrs: Any,
    ) -> Topology:
        """
        Generate a small-world network topology using Watts-Strogatz model.

        Args:
            n_nodes: Total number of nodes.
            k_neighbors: Each node is joined with its k nearest neighbors in a ring.
            rewire_prob: The probability of rewiring each edge.
            seed: Random seed for reproducibility.
            default_attrs: Optional override attributes.
        """
        if n_nodes <= k_neighbors:
            raise TopologyError("Number of nodes must be greater than k_neighbors.")
        if not (0.0 <= rewire_prob <= 1.0):
            raise TopologyError("Rewire probability must be between 0.0 and 1.0.")

        rng = get_rng(seed)

        undirected = nx.watts_strogatz_graph(n_nodes, k_neighbors, rewire_prob, seed=seed)
        directed = nx.DiGraph(undirected)

        # Relabel nodes to strings
        mapping = {node: str(node) for node in directed.nodes}
        directed = cast("nx.DiGraph", nx.relabel_nodes(directed, mapping))

        cls._assign_default_node_attrs(directed, "router", rng, **default_attrs)
        cls._assign_random_edge_attrs(directed, rng, **default_attrs)

        return Topology(directed)

    @classmethod
    def fat_tree(cls, k: int, seed: int | None = None, **default_attrs: Any) -> Topology:
        """
        Generate a k-ary Fat-Tree data center topology.

        A k-ary fat-tree consists of k pods.
        - Core layer: (k/2)^2 nodes
        - Each pod has:
          - k/2 aggregation switches
          - k/2 edge switches
          - (k/2)^2 hosts
        - Links connect hosts to edge, edge to aggregation, aggregation to core.

        Args:
            k: Port count of each switch (must be an even integer >= 2).
            seed: Random seed for reproducibility.
            default_attrs: Optional override attributes.
        """
        if k % 2 != 0 or k < 2:
            raise TopologyError("Fat-Tree port count k must be an even integer >= 2.")

        graph = nx.DiGraph()

        # 1. Add Core switches
        core_nodes = cls._add_fat_tree_core_layer(graph, k)

        # 2. Add pod switches and hosts
        for pod_idx in range(k):
            cls._add_fat_tree_pod(graph, k, pod_idx, core_nodes, **default_attrs)

        # 3. Fill in any missing or customized attributes
        for src, dst in graph.edges:
            # Overwrite default parameters if specifically provided in kwargs
            for k_attr, v_attr in default_attrs.items():
                if not k_attr.endswith("bandwidth") and not k_attr.endswith("latency"):
                    graph.edges[src, dst][k_attr] = v_attr

        return Topology(graph)

    @classmethod
    def from_adjacency_matrix(
        cls,
        matrix: np.ndarray,
        node_labels: list[str] | None = None,
        seed: int | None = None,
        **default_attrs: Any,
    ) -> Topology:
        """
        Generate a topology from a NumPy adjacency matrix.

        Args:
            matrix: Adjacency matrix where matrix[i, j] > 0 means a link from i to j exists.
            node_labels: Optional labels for nodes. Defaults to "0", "1", "2", ...
            seed: Random seed for reproducibility.
            default_attrs: Optional override attributes.
        """
        rows, cols = matrix.shape
        if rows != cols:
            raise TopologyError("Adjacency matrix must be square.")

        rng = get_rng(seed)
        graph = nx.DiGraph()

        if node_labels is None:
            node_labels = [str(i) for i in range(rows)]
        elif len(node_labels) != rows:
            raise TopologyError("Length of node_labels must match matrix dimensions.")

        for label in node_labels:
            graph.add_node(label)

        for i in range(rows):
            for j in range(cols):
                if matrix[i, j] > 0:
                    graph.add_edge(node_labels[i], node_labels[j])

        cls._assign_default_node_attrs(graph, "router", rng, **default_attrs)
        cls._assign_random_edge_attrs(graph, rng, **default_attrs)

        return Topology(graph)
