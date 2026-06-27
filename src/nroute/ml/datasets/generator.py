"""Dataset generator for compiling simulation traces and GNN datasets."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import pandas as pd

from nroute.ml.features.builder import FeatureBuilder
from nroute.routing import get_router
from nroute.simulation.engine import SimulationEngine
from nroute.simulation.traffic_gen import TrafficGenerator

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class DatasetGenerator:
    """Runs simulations and compiles telemetry snapshots into JSON & Parquet formats."""

    def __init__(
        self,
        topology: Topology,
        router_alg: str = "dijkstra",
        traffic_model: str = "uniform",
        duration_ticks: int = 100,
        flows_per_tick: int = 5,
        seed: int | None = None,
    ) -> None:
        """
        Initialize the DatasetGenerator.

        Args:
            topology: Base network topology.
            router_alg: Routing algorithm to use during simulation.
            traffic_model: Traffic matrix generator pattern name.
            duration_ticks: Number of ticks to simulate.
            flows_per_tick: Flow volume per tick.
            seed: Global seed for reproducibility.
        """
        self.topology = topology
        self.router_alg = router_alg
        self.traffic_model = traffic_model
        self.duration_ticks = duration_ticks
        self.flows_per_tick = flows_per_tick
        self.seed = seed

    def generate_snapshots(self) -> list[dict[str, Any]]:
        """
        Run the simulation and collect snapshot data at each tick.

        Returns:
            List of raw snapshot dictionaries.
        """
        snapshots: list[dict[str, Any]] = []

        router = get_router(self.router_alg, self.topology)
        traffic_gen = TrafficGenerator(
            self.traffic_model, n_flows_per_tick=self.flows_per_tick, seed=self.seed
        )

        engine = SimulationEngine(
            topology=self.topology,
            router=router,
            traffic_generator=traffic_gen,
        )

        def tick_callback(tick: int, sim: SimulationEngine) -> None:
            # Gather node details
            nodes_data = []
            for node in sim.topology.nodes:
                attrs = sim.topology.get_node(node)
                nodes_data.append(
                    {
                        "id": node,
                        "capacity": float(attrs.get("capacity", 1000.0)),
                        "status": attrs.get("status", "up"),
                        "queue_length": float(attrs.get("queue_length", 0.0)),
                        "packet_load": float(attrs.get("packet_load", 0.0)),
                    }
                )

            # Gather edge details
            edges_data = []
            for u, v in sim.topology.edges:
                attrs = sim.topology.get_edge(u, v)
                edges_data.append(
                    {
                        "source": u,
                        "destination": v,
                        "bandwidth": float(attrs.get("bandwidth", 1000.0)),
                        "latency": float(attrs.get("latency", 5.0)),
                        "utilization": float(attrs.get("utilization", 0.0)),
                        "packet_loss": float(attrs.get("packet_loss", 0.0)),
                        "status": attrs.get("status", "up"),
                        "reliability": float(attrs.get("reliability", 1.0)),
                        "failure_frequency": float(attrs.get("failure_frequency", 0.0)),
                    }
                )

            # Gather traffic completed in this tick
            traffic_data = []
            for flow in sim.last_tick_completed_flows:
                traffic_data.append(
                    {
                        "source": flow.source,
                        "destination": flow.destination,
                        "bytes": flow.bytes,
                        "packets": flow.packets,
                        "protocol": flow.protocol,
                    }
                )

            # Gather global metrics of this tick
            results = sim.collector.get_results()
            throughput = 0.0
            avg_latency = 0.0
            loss_rate = 0.0
            if results.results:
                # Get the last recorded tick metric
                last_m = results.results[-1]
                throughput = last_m.throughput
                avg_latency = last_m.avg_latency
                loss_rate = last_m.packet_loss_rate

            snapshot = {
                "tick": tick,
                "nodes": nodes_data,
                "edges": edges_data,
                "traffic": traffic_data,
                "global_metrics": {
                    "throughput": throughput,
                    "avg_latency": avg_latency,
                    "packet_loss_rate": loss_rate,
                },
            }
            snapshots.append(snapshot)

        # Run simulation
        engine.run(
            duration_ticks=self.duration_ticks,
            seed=self.seed,
            callback=tick_callback,
            show_progress=False,
        )

        return snapshots

    def save_json_snapshots(
        self, snapshots: list[dict[str, Any]], filepath: str
    ) -> None:
        """Save collected snapshots to a JSON file."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(snapshots, f, indent=2)

    def compile_to_parquet(
        self, snapshots: list[dict[str, Any]], output_dir: str
    ) -> None:
        """
        Compile JSON snapshots into DataFrames and save as Parquet files.

        Args:
            snapshots: List of snapshot dictionaries.
            output_dir: Directory where parquet files will be saved.
        """
        os.makedirs(output_dir, exist_ok=True)

        node_records = []
        edge_records = []
        global_records = []

        feature_builder = FeatureBuilder()

        # Re-create Topology objects from snapshots to extract centralities and features cleanly
        # using our FeatureBuilder.
        from nroute.core.topology import Topology

        for snap in snapshots:
            tick = snap["tick"]

            # Reconstruct topology for this tick
            topo = Topology()
            for n_dict in snap["nodes"]:
                node_id = n_dict["id"]
                topo.add_node(
                    node_id,
                    capacity=n_dict["capacity"],
                    status=n_dict["status"],
                    queue_length=n_dict["queue_length"],
                    packet_load=n_dict["packet_load"],
                )

            for e_dict in snap["edges"]:
                topo.add_edge(
                    e_dict["source"],
                    e_dict["destination"],
                    bandwidth=e_dict["bandwidth"],
                    latency=e_dict["latency"],
                    utilization=e_dict["utilization"],
                    packet_loss=e_dict["packet_loss"],
                    status=e_dict["status"],
                    reliability=e_dict.get("reliability", 1.0),
                    failure_frequency=e_dict.get("failure_frequency", 0.0),
                )

            # Build rich feature tensors
            bundle = feature_builder.build_features(topo)
            nodes_sorted = sorted(topo.nodes)
            edges_sorted = sorted(topo.edges)

            # Compile Node Features
            for idx, node_id in enumerate(nodes_sorted):
                n_feats = bundle.node_features[idx]
                node_records.append(
                    {
                        "tick": tick,
                        "node_id": node_id,
                        "capacity": float(n_feats[0]),
                        "status": float(n_feats[1]),
                        "degree": float(n_feats[2]),
                        "queue_length": float(n_feats[3]),
                        "packet_load": float(n_feats[4]),
                        "congestion_score": float(n_feats[5]),
                        "betweenness_centrality": float(n_feats[6]),
                        "closeness_centrality": float(n_feats[7]),
                    }
                )

            # Compile Edge Features
            for idx, (src, dst) in enumerate(edges_sorted):
                e_feats = bundle.edge_features[idx]
                utilization = float(e_feats[2])
                node_to_idx = bundle.node_to_idx
                # Label is 1 if utilization >= 0.85
                congested_label = 1 if utilization >= 0.85 else 0

                edge_records.append(
                    {
                        "tick": tick,
                        "source": src,
                        "destination": dst,
                        "source_idx": node_to_idx[src],
                        "destination_idx": node_to_idx[dst],
                        "bandwidth": float(e_feats[0]),
                        "latency": float(e_feats[1]),
                        "utilization": utilization,
                        "packet_loss": float(e_feats[3]),
                        "reliability": float(e_feats[4]),
                        "failure_frequency": float(e_feats[5]),
                        "congested_label": congested_label,
                    }
                )

            # Compile Global Features
            gm = snap["global_metrics"]
            global_records.append(
                {
                    "tick": tick,
                    "throughput": gm["throughput"],
                    "avg_latency": gm["avg_latency"],
                    "packet_loss_rate": gm["packet_loss_rate"],
                }
            )

        # Write Parquet files
        pd.DataFrame(node_records).to_parquet(
            os.path.join(output_dir, "node_features.parquet")
        )
        pd.DataFrame(edge_records).to_parquet(
            os.path.join(output_dir, "edge_features.parquet")
        )
        pd.DataFrame(global_records).to_parquet(
            os.path.join(output_dir, "global_metrics.parquet")
        )

    @staticmethod
    def load_parquet_dataset(
        dataset_dir: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Load node, edge, and global metrics DataFrames from parquet."""
        node_df = pd.read_parquet(os.path.join(dataset_dir, "node_features.parquet"))
        edge_df = pd.read_parquet(os.path.join(dataset_dir, "edge_features.parquet"))
        global_df = pd.read_parquet(os.path.join(dataset_dir, "global_metrics.parquet"))
        return node_df, edge_df, global_df
