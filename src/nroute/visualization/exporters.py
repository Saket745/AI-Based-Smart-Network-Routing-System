"""Data exporting utilities for network topologies and simulation metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx
import pandas as pd

from nroute.core.metrics import MetricsCollectionResult, SimulationMetrics
from nroute.exceptions import SimulationError

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class TopologyExporter:
    """Exporter for network topologies."""

    @staticmethod
    def to_json(topology: Topology, path: str | Path) -> None:
        """Export topology graph to JSON file."""
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(topology.to_dict(), f, indent=2)
        except Exception as e:
            raise SimulationError(
                f"Failed to export topology to JSON {path}: {e}"
            ) from e

    @staticmethod
    def to_graphml(topology: Topology, path: str | Path) -> None:
        """Export topology graph to GraphML file for tool interoperability (Gephi/Cytoscape)."""
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            # Create a copy to prevent mutating the original topology graph attributes
            g_copy = topology.graph.copy()
            # Convert attributes that are lists or dicts to strings, and remove None values to satisfy GraphML schema
            for _, ndata in g_copy.nodes(data=True):
                for k, v in list(ndata.items()):
                    if v is None:
                        del ndata[k]
                    elif isinstance(v, (list, dict)):
                        ndata[k] = json.dumps(v)
            for _, _, edata in g_copy.edges(data=True):
                for k, v in list(edata.items()):
                    if v is None:
                        del edata[k]
                    elif isinstance(v, (list, dict)):
                        edata[k] = json.dumps(v)

            nx.write_graphml(g_copy, str(p))
        except Exception as e:
            raise SimulationError(
                f"Failed to export topology to GraphML {path}: {e}"
            ) from e

    @staticmethod
    def to_csv(topology: Topology, path: str | Path) -> None:
        """Export topology to separate node and edge CSV files."""
        p = Path(path)
        base_name = p.stem
        dir_name = p.parent
        ext = p.suffix or ".csv"

        nodes_path = dir_name / f"{base_name}_nodes{ext}"
        edges_path = dir_name / f"{base_name}_edges{ext}"

        try:
            dir_name.mkdir(parents=True, exist_ok=True)

            # Node DataFrame
            nodes_data = []
            for node_id, data in topology.graph.nodes(data=True):
                row = {"node_id": node_id}
                row.update(data)
                nodes_data.append(row)
            pd.DataFrame(nodes_data).to_csv(nodes_path, index=False)

            # Edge DataFrame
            edges_data = []
            for u, v, data in topology.graph.edges(data=True):
                row = {"source": u, "target": v}
                row.update(data)
                edges_data.append(row)
            pd.DataFrame(edges_data).to_csv(edges_path, index=False)

        except Exception as e:
            raise SimulationError(
                f"Failed to export topology to CSV {path}: {e}"
            ) from e


class MetricsExporter:
    """Exporter for simulation metrics."""

    @staticmethod
    def to_json(
        metrics: MetricsCollectionResult
        | list[SimulationMetrics]
        | list[dict[str, Any]],
        path: str | Path,
    ) -> None:
        """Export simulation metrics to JSON file."""
        p = Path(path)
        if isinstance(metrics, MetricsCollectionResult):
            metrics.to_json(p)
        else:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                raw_list = []
                for item in metrics:
                    if isinstance(item, SimulationMetrics):
                        raw_list.append(item.model_dump())
                    else:
                        raw_list.append(item)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(raw_list, f, indent=2)
            except Exception as e:
                raise SimulationError(
                    f"Failed to export metrics to JSON {path}: {e}"
                ) from e

    @staticmethod
    def to_csv(
        metrics: MetricsCollectionResult
        | list[SimulationMetrics]
        | list[dict[str, Any]],
        path: str | Path,
    ) -> None:
        """Export simulation metrics to CSV file."""
        p = Path(path)
        if isinstance(metrics, MetricsCollectionResult):
            metrics.to_csv(p)
        else:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                raw_list = []
                for item in metrics:
                    if isinstance(item, SimulationMetrics):
                        raw_list.append(item.model_dump())
                    else:
                        raw_list.append(item)
                pd.DataFrame(raw_list).to_csv(p, index=False)
            except Exception as e:
                raise SimulationError(
                    f"Failed to export metrics to CSV {path}: {e}"
                ) from e
