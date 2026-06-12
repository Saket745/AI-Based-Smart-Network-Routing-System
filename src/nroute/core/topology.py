"""Topology data structure wrapping NetworkX DiGraph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import networkx as nx

from nroute.exceptions import TopologyError, ValidationError
from nroute.utils.validators import (
    validate_node_id,
    validate_positive_float,
    validate_probability,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# Type aliases for nodes and edges
NodeDict = dict[str, Any]
EdgeDict = dict[str, Any]


class Topology:
    """
    Wraps networkx.DiGraph and enforces node/edge schemas and validation rules.
    """

    # Valid node types
    NODE_TYPES = frozenset({"router", "switch", "host", "gateway"})

    # Valid edge statuses
    EDGE_STATUSES = frozenset({"up", "down", "degraded"})

    # Valid node statuses
    NODE_STATUSES = frozenset({"up", "down"})

    def __init__(self, graph: nx.DiGraph | None = None) -> None:
        """Initialize Topology instance."""
        self._graph = graph if graph is not None else nx.DiGraph()

    @property
    def graph(self) -> nx.DiGraph:
        """Get the underlying networkx DiGraph instance."""
        return self._graph

    @property
    def nodes(self) -> list[str]:
        """Get the list of node IDs in the topology."""
        return list(self._graph.nodes)

    @property
    def edges(self) -> list[tuple[str, str]]:
        """Get the list of edges (src, dst) in the topology."""
        return list(self._graph.edges)

    @property
    def node_count(self) -> int:
        """Get the total number of nodes in the topology."""
        return cast("int", self._graph.number_of_nodes())

    @property
    def edge_count(self) -> int:
        """Get the total number of edges in the topology."""
        return cast("int", self._graph.number_of_edges())

    def neighbors(self, node_id: str) -> list[str]:
        """
        Get the list of neighbors for a node.

        Args:
            node_id: ID of the node.

        Returns:
            List of successor node IDs.

        Raises:
            TopologyError: If the node does not exist.
        """
        if node_id not in self._graph:
            raise TopologyError(f"Node '{node_id}' does not exist in topology.")
        return list(self._graph.successors(node_id))

    def add_node(self, node_id: str, **attrs: Any) -> None:
        """
        Add a node with validated attributes.

        Args:
            node_id: ID of the node.
            attrs: Node attributes to set.

        Raises:
            ValidationError: If any attribute value is invalid.
        """
        validated_id = validate_node_id(node_id)

        # Merge with defaults
        node_type = attrs.get("type", "router")
        if node_type not in self.NODE_TYPES:
            raise ValidationError(
                f"Node type '{node_type}' is invalid. Must be one of {self.NODE_TYPES}."
            )

        capacity = validate_positive_float(attrs.get("capacity", 1000.0), "capacity")

        status = attrs.get("status", "up")
        if status not in self.NODE_STATUSES:
            raise ValidationError(
                f"Node status '{status}' is invalid. Must be one of {self.NODE_STATUSES}."
            )

        location = attrs.get("location")
        if location is not None and not isinstance(location, str):
            raise ValidationError(f"Node location must be a string, got {type(location).__name__}.")

        validated_attrs = {
            "type": node_type,
            "capacity": capacity,
            "status": status,
            "location": location,
        }

        # Preserve any extra custom attributes the user passes
        for k, v in attrs.items():
            if k not in validated_attrs:
                validated_attrs[k] = v

        self._graph.add_node(validated_id, **validated_attrs)

    def remove_node(self, node_id: str) -> None:
        """
        Remove a node and all of its incident edges.

        Args:
            node_id: ID of the node to remove.

        Raises:
            TopologyError: If the node does not exist.
        """
        if node_id not in self._graph:
            raise TopologyError(f"Node '{node_id}' does not exist.")
        self._graph.remove_node(node_id)

    def get_node(self, node_id: str) -> NodeDict:
        """
        Get attributes of a node.

        Args:
            node_id: ID of the node.

        Returns:
            Dictionary of node attributes.

        Raises:
            TopologyError: If the node does not exist.
        """
        if node_id not in self._graph:
            raise TopologyError(f"Node '{node_id}' does not exist.")
        return dict(self._graph.nodes[node_id])

    def add_edge(self, src: str, dst: str, **attrs: Any) -> None:
        """
        Add a directed edge with validated attributes.

        Args:
            src: Source node ID.
            dst: Destination node ID.
            attrs: Edge attributes to set.

        Raises:
            ValidationError: If attributes are invalid.
            TopologyError: If src or dst nodes do not exist.
        """
        if src not in self._graph:
            raise TopologyError(f"Source node '{src}' does not exist.")
        if dst not in self._graph:
            raise TopologyError(f"Destination node '{dst}' does not exist.")

        bandwidth = validate_positive_float(attrs.get("bandwidth", 1000.0), "bandwidth")
        latency = validate_positive_float(attrs.get("latency", 5.0), "latency")
        jitter = validate_positive_float(attrs.get("jitter", 0.0), "jitter")
        packet_loss = validate_probability(attrs.get("packet_loss", 0.0))
        utilization = validate_probability(attrs.get("utilization", 0.0))
        weight = validate_positive_float(attrs.get("weight", latency), "weight")

        status = attrs.get("status", "up")
        if status not in self.EDGE_STATUSES:
            raise ValidationError(
                f"Edge status '{status}' is invalid. Must be one of {self.EDGE_STATUSES}."
            )

        validated_attrs = {
            "bandwidth": bandwidth,
            "latency": latency,
            "jitter": jitter,
            "packet_loss": packet_loss,
            "utilization": utilization,
            "weight": weight,
            "status": status,
        }

        # Preserve any extra custom attributes
        for k, v in attrs.items():
            if k not in validated_attrs:
                validated_attrs[k] = v

        self._graph.add_edge(src, dst, **validated_attrs)

    def remove_edge(self, src: str, dst: str) -> None:
        """
        Remove a directed edge.

        Args:
            src: Source node ID.
            dst: Destination node ID.

        Raises:
            TopologyError: If the edge does not exist.
        """
        if not self._graph.has_edge(src, dst):
            raise TopologyError(f"Edge from '{src}' to '{dst}' does not exist.")
        self._graph.remove_edge(src, dst)

    def get_edge(self, src: str, dst: str) -> EdgeDict:
        """
        Get attributes of an edge.

        Args:
            src: Source node ID.
            dst: Destination node ID.

        Returns:
            Dictionary of edge attributes.

        Raises:
            TopologyError: If the edge does not exist.
        """
        if not self._graph.has_edge(src, dst):
            raise TopologyError(f"Edge from '{src}' to '{dst}' does not exist.")
        return dict(self._graph.edges[src, dst])

    def update_edge(self, src: str, dst: str, **attrs: Any) -> None:
        """
        Update dynamic attributes on an edge. Enforces schema validation.

        Args:
            src: Source node ID.
            dst: Destination node ID.
            attrs: Edge attributes to update.

        Raises:
            TopologyError: If the edge does not exist.
            ValidationError: If attribute values violate constraints.
        """
        if not self._graph.has_edge(src, dst):
            raise TopologyError(f"Edge from '{src}' to '{dst}' does not exist.")

        edge_data = self._graph.edges[src, dst]

        # Validate provided attributes
        updated_data: dict[str, Any] = {}

        if "bandwidth" in attrs:
            updated_data["bandwidth"] = validate_positive_float(attrs["bandwidth"], "bandwidth")
        if "latency" in attrs:
            updated_data["latency"] = validate_positive_float(attrs["latency"], "latency")
        if "jitter" in attrs:
            updated_data["jitter"] = validate_positive_float(attrs["jitter"], "jitter")
        if "packet_loss" in attrs:
            updated_data["packet_loss"] = validate_probability(attrs["packet_loss"])
        if "utilization" in attrs:
            updated_data["utilization"] = validate_probability(attrs["utilization"])
        if "weight" in attrs:
            updated_data["weight"] = validate_positive_float(attrs["weight"], "weight")
        if "status" in attrs:
            status = attrs["status"]
            if status not in self.EDGE_STATUSES:
                raise ValidationError(
                    f"Edge status '{status}' is invalid. Must be one of {self.EDGE_STATUSES}."
                )
            updated_data["status"] = status

        # Merge other attributes
        for k, v in attrs.items():
            if k not in {
                "bandwidth",
                "latency",
                "jitter",
                "packet_loss",
                "utilization",
                "weight",
                "status",
            }:
                updated_data[k] = v

        # Apply update
        edge_data.update(updated_data)

    def set_link_down(self, src: str, dst: str) -> None:
        """Mark a link's status as down."""
        self.update_edge(src, dst, status="down")

    def set_link_up(self, src: str, dst: str) -> None:
        """Mark a link's status as up."""
        self.update_edge(src, dst, status="up")

    def set_node_down(self, node_id: str) -> None:
        """Mark a node's status as down and all of its incident links as down."""
        if node_id not in self._graph:
            raise TopologyError(f"Node '{node_id}' does not exist.")
        self._graph.nodes[node_id]["status"] = "down"

        # Mark all incoming and outgoing links as down
        for successor in list(self._graph.successors(node_id)):
            self.update_edge(node_id, successor, status="down")
        for predecessor in list(self._graph.predecessors(node_id)):
            self.update_edge(predecessor, node_id, status="down")

    def set_node_up(self, node_id: str) -> None:
        """Mark a node's status as up and all of its incident links as up."""
        if node_id not in self._graph:
            raise TopologyError(f"Node '{node_id}' does not exist.")
        self._graph.nodes[node_id]["status"] = "up"

        # Mark incident links back up
        for successor in list(self._graph.successors(node_id)):
            self.update_edge(node_id, successor, status="up")
        for predecessor in list(self._graph.predecessors(node_id)):
            self.update_edge(predecessor, node_id, status="up")

    def copy(self) -> Topology:
        """Create a deep copy of the topology."""
        return Topology(self._graph.copy())

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize topology to a JSON-serializable dictionary.

        Format:
        {
            "nodes": [{"id": "node_id", "type": "...", ...}, ...],
            "edges": [{"source": "src", "target": "dst", "bandwidth": ..., ...}, ...]
        }
        """
        nodes = []
        for node_id, attrs in self._graph.nodes(data=True):
            node_dict = {"id": node_id}
            node_dict.update(attrs)
            nodes.append(node_dict)

        edges = []
        for src, dst, attrs in self._graph.edges(data=True):
            edge_dict = {"source": src, "target": dst}
            edge_dict.update(attrs)
            edges.append(edge_dict)

        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Topology:
        """
        Reconstruct a Topology instance from a dictionary.

        Args:
            data: Dictionary serialized via to_dict().

        Returns:
            A new Topology instance.
        """
        topo = cls()
        nodes = data.get("nodes", [])
        for node in nodes:
            node_id = node.get("id")
            if not node_id:
                raise TopologyError("Node data is missing 'id' attribute.")
            attrs = {k: v for k, v in node.items() if k != "id"}
            topo.add_node(node_id, **attrs)

        edges = data.get("edges", [])
        for edge in edges:
            src = edge.get("source")
            dst = edge.get("target")
            if not src or not dst:
                raise TopologyError("Edge data is missing 'source' or 'target' attribute.")
            attrs = {k: v for k, v in edge.items() if k not in {"source", "target"}}
            topo.add_edge(src, dst, **attrs)

        return topo

    def save(self, path: str | Path) -> None:
        """
        Save the topology to a JSON file.

        Args:
            path: Path to the target file.
        """
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            raise TopologyError(f"Failed to save topology to {path}: {e}") from e

    @classmethod
    def load(cls, path: str | Path) -> Topology:
        """
        Load a topology from a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            Reconstructed Topology instance.
        """
        p = Path(path)
        if not p.is_file():
            raise TopologyError(f"Topology file does not exist: {path}")
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            if isinstance(e, TopologyError):
                raise
            raise TopologyError(f"Failed to load topology from {path}: {e}") from e

    def summary(self) -> str:
        """
        Get a structured string summary of the topology.

        Returns:
            A multiline summary string.
        """
        if self.node_count == 0:
            return "Empty Topology (0 nodes, 0 edges)"

        # Calculate attribute ranges
        latencies = [
            attrs["latency"] for _, _, attrs in self._graph.edges(data=True) if "latency" in attrs
        ]
        bandwidths = [
            attrs["bandwidth"]
            for _, _, attrs in self._graph.edges(data=True)
            if "bandwidth" in attrs
        ]
        utilizations = [
            attrs["utilization"]
            for _, _, attrs in self._graph.edges(data=True)
            if "utilization" in attrs
        ]

        min_lat = min(latencies) if latencies else 0.0
        max_lat = max(latencies) if latencies else 0.0
        min_bw = min(bandwidths) if bandwidths else 0.0
        max_bw = max(bandwidths) if bandwidths else 0.0
        min_util = min(utilizations) if utilizations else 0.0
        max_util = max(utilizations) if utilizations else 0.0

        down_nodes = sum(
            1 for _, attrs in self._graph.nodes(data=True) if attrs.get("status") == "down"
        )
        down_links = sum(
            1 for _, _, attrs in self._graph.edges(data=True) if attrs.get("status") == "down"
        )

        return (
            f"Topology Summary:\n"
            f"-----------------\n"
            f"Nodes: {self.node_count} ({down_nodes} down)\n"
            f"Edges: {self.edge_count} ({down_links} down)\n"
            f"Latency range: {min_lat:.1f}ms to {max_lat:.1f}ms\n"
            f"Bandwidth range: {min_bw:.1f}Mbps to {max_bw:.1f}Mbps\n"
            f"Utilization range: {min_util*100:.1f}% to {max_util*100:.1f}%\n"
        )

    @classmethod
    def generate(cls, type: str, **kwargs: Any) -> Topology:
        """
        Convenience factory to generate a topology using generators.

        Args:
            type: Type of topology ('random', 'scale-free', 'small-world', 'fat-tree').
            kwargs: Generator-specific arguments.
        """
        from nroute.core.generators import TopologyGenerator

        t = type.lower().strip()
        if t == "random":
            n_nodes = kwargs.pop("n_nodes", 50)
            edge_prob = kwargs.pop("edge_prob", 0.1)
            seed = kwargs.pop("seed", None)
            return TopologyGenerator.random(n_nodes, edge_prob, seed=seed, **kwargs)
        elif t == "scale-free":
            n_nodes = kwargs.pop("n_nodes", 50)
            seed = kwargs.pop("seed", None)
            return TopologyGenerator.scale_free(n_nodes, seed=seed, **kwargs)
        elif t == "small-world":
            n_nodes = kwargs.pop("n_nodes", 50)
            k_neighbors = kwargs.pop("k_neighbors", 4)
            rewire_prob = kwargs.pop("rewire_prob", 0.1)
            seed = kwargs.pop("seed", None)
            return TopologyGenerator.small_world(
                n_nodes, k_neighbors, rewire_prob, seed=seed, **kwargs
            )
        elif t == "fat-tree":
            k = kwargs.pop("k", 4)
            seed = kwargs.pop("seed", None)
            return TopologyGenerator.fat_tree(k, seed=seed, **kwargs)
        else:
            raise TopologyError(
                f"Unknown topology type '{type}'. Must be one of: "
                "random, scale-free, small-world, fat-tree."
            )

    @classmethod
    def from_csv(cls, path: str | Path) -> Topology:
        """Load topology from a CSV edge-list file."""
        from nroute.ingestion import ingest

        result = ingest(path, format="csv-topology")
        if not isinstance(result, Topology):
            raise TopologyError("Ingested data is not a Topology.")
        return result

    @classmethod
    def from_json(cls, path: str | Path) -> Topology:
        """Load topology from a JSON file."""
        from nroute.ingestion import ingest

        result = ingest(path, format="json-topology")
        if not isinstance(result, Topology):
            raise TopologyError("Ingested data is not a Topology.")
        return result

    @classmethod
    def from_netflow(cls, path: str | Path) -> Topology:
        """
        Build topology dynamically from NetFlow flow records.
        Discovers nodes and edges from flow source/destination endpoints.
        """
        from nroute.core.traffic import TrafficMatrix
        from nroute.ingestion import ingest

        result = ingest(path, format="netflow")
        if not isinstance(result, TrafficMatrix):
            raise TopologyError("Ingested data is not a TrafficMatrix.")

        # Build topology from traffic matrix endpoints
        topo = cls()
        for flow in result.flows:
            if flow.source not in topo.nodes:
                topo.add_node(flow.source)
            if flow.destination not in topo.nodes:
                topo.add_node(flow.destination)
            if (flow.source, flow.destination) not in topo.edges:
                topo.add_edge(flow.source, flow.destination)
        return topo

    def compute_routes(
        self,
        traffic_matrix: Any,
        router: str | Any = "dijkstra",
        weight: str | Callable[[dict[str, Any]], float] | None = None,
    ) -> dict[tuple[str, str], list[str]]:
        """
        Compute paths for all flow records in a traffic matrix.

        Args:
            traffic_matrix: The traffic matrix containing flow demands.
            router: A BaseRouter instance or router name ("dijkstra" | "bellman-ford" | "ecmp").
            weight: Edge attribute name or weight function to use as routing metric.

        Returns:
            A dictionary mapping (source, destination) to the computed path.
        """
        from nroute.routing import BaseRouter, get_router

        r_inst: BaseRouter = get_router(router, self) if isinstance(router, str) else router

        return r_inst.compute_routes(self, traffic_matrix, weight=weight)
