"""Traffic generators for simulating network traffic patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nroute.core.traffic import FlowRecord
from nroute.utils.random import get_rng

if TYPE_CHECKING:
    from nroute.core.topology import Topology


class TrafficGenerator:
    """
    Generates synthetic traffic flows using different models (uniform, gravity, hotspot, bursty).
    """

    def __init__(
        self,
        model: str = "uniform",
        n_flows_per_tick: int = 5,
        seed: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the TrafficGenerator.

        Args:
            model: "uniform" | "gravity" | "hotspot" | "bursty".
            n_flows_per_tick: Base number of flows generated per simulation tick.
            seed: Random seed for reproducibility.
            kwargs: Extra parameters for specific models (e.g., hotspot_nodes, burst_prob).
        """
        self.model = model.lower().strip()
        self.n_flows_per_tick = n_flows_per_tick
        self.seed = seed
        self.rng = get_rng(seed)
        self.kwargs = kwargs

    def set_seed(self, seed: int | None) -> None:
        """Set random seed for reproducibility."""
        self.seed = seed
        self.rng = get_rng(seed)

    def generate(self, topology: Topology, tick: int = 0) -> list[FlowRecord]:
        """
        Generate a list of FlowRecord objects for the current tick.

        Args:
            topology: The network topology.
            tick: The current simulation tick index.
        """
        if topology.node_count < 2:
            return []

        if self.model == "uniform":
            return self._generate_uniform(topology, tick)
        elif self.model == "gravity":
            return self._generate_gravity(topology, tick)
        elif self.model == "hotspot":
            return self._generate_hotspot(topology, tick)
        elif self.model == "bursty":
            return self._generate_bursty(topology, tick)
        else:
            raise ValueError(f"Unknown traffic model '{self.model}'.")

    def _create_flow(
        self, src: str, dst: str, tick: int, bytes_multiplier: float = 1.0
    ) -> FlowRecord:
        """Helper to create a single FlowRecord with realistic metrics."""
        # Random flow sizes
        bytes_val = int(self.rng.randint(1000, 1000000) * bytes_multiplier)
        pkts_val = max(1, bytes_val // self.rng.randint(500, 1450))
        duration = round(self.rng.uniform(0.1, 10.0), 3)

        # Weighted protocols: TCP (70%), UDP (25%), ICMP (5%)
        proto = self.rng.choices(["TCP", "UDP", "ICMP"], weights=[0.70, 0.25, 0.05], k=1)[0]
        timestamp = float(tick)

        return FlowRecord(
            source=src,
            destination=dst,
            bytes=bytes_val,
            packets=pkts_val,
            duration=duration,
            protocol=proto,
            timestamp=timestamp,
        )

    def _generate_uniform(self, topology: Topology, tick: int) -> list[FlowRecord]:
        """Generate flows where endpoints are chosen uniformly at random."""
        nodes = topology.nodes
        if len(nodes) < 2:
            return []

        flows = []
        for _ in range(self.n_flows_per_tick):
            src = self.rng.choice(nodes)
            # Re-sample dst in O(1) expected time until dst != src, avoiding O(V) list allocations per flow.
            dst = self.rng.choice(nodes)
            while dst == src:
                dst = self.rng.choice(nodes)
            flows.append(self._create_flow(src, dst, tick))

        return flows

    def _generate_gravity(self, topology: Topology, tick: int) -> list[FlowRecord]:
        """
        Generate flows where traffic demand between u and v is proportional
        to Capacity(u) * Capacity(v).
        """
        nodes = topology.nodes
        if len(nodes) < 2:
            return []

        # Access topology.graph.nodes directly to avoid O(V) dict copying overhead per node.
        g_nodes = topology.graph.nodes
        node_weights = [
            max(1.0, float(g_nodes[node].get("capacity", 1000.0))) for node in nodes
        ]

        flows = []
        # Joint pair rejection sampling: sample src and dst independently weighted by capacity
        # and reject when src == dst. This preserves the exact joint probability distribution
        # P(src=u, dst=v) proportional to C_u * C_v while avoiding generating O(V^2) pairs per tick.
        for _ in range(self.n_flows_per_tick):
            while True:
                src = self.rng.choices(nodes, weights=node_weights, k=1)[0]
                dst = self.rng.choices(nodes, weights=node_weights, k=1)[0]
                if src != dst:
                    break
            flows.append(self._create_flow(src, dst, tick))

        return flows

    def _generate_hotspot(self, topology: Topology, tick: int) -> list[FlowRecord]:
        """
        Generate flows where 80% of traffic targets a set of hotspot nodes.
        """
        nodes = topology.nodes
        if len(nodes) < 2:
            return []

        hotspots: list[str] = self.kwargs.get("hotspot_nodes", [])

        # If no hotspots specified, select top 20% capacity nodes as hotspots
        if not hotspots:
            g_nodes = topology.graph.nodes
            sorted_nodes = sorted(
                nodes,
                key=lambda n: float(g_nodes[n].get("capacity", 1000.0)),
                reverse=True,
            )
            k = max(1, len(nodes) // 5)
            hotspots = sorted_nodes[:k]

        non_hotspots = [n for n in nodes if n not in hotspots]
        if not non_hotspots:
            # Fallback to uniform if all are hotspots
            return self._generate_uniform(topology, tick)

        flows = []
        for _ in range(self.n_flows_per_tick):
            # 80% probability destination is a hotspot
            if self.rng.random_float() < 0.80 and hotspots:
                dst = self.rng.choice(hotspots)
            else:
                dst = self.rng.choice(non_hotspots)

            # Re-sample src in O(1) expected time until src != dst, avoiding O(V) list allocations per flow.
            src = self.rng.choice(nodes)
            while src == dst:
                src = self.rng.choice(nodes)
            flows.append(self._create_flow(src, dst, tick))

        return flows

    def _generate_bursty(self, topology: Topology, tick: int) -> list[FlowRecord]:
        """
        Generate traffic that periodically spikes in count and size.
        """
        nodes = topology.nodes
        if len(nodes) < 2:
            return []

        burst_prob = float(self.kwargs.get("burst_prob", 0.15))
        burst_multiplier = float(self.kwargs.get("burst_multiplier", 5.0))

        is_burst = self.rng.random_float() < burst_prob
        count = int(self.n_flows_per_tick * (burst_multiplier if is_burst else 1.0))
        bytes_mult = self.rng.uniform(2.0, 8.0) if is_burst else 1.0

        flows = []
        for _ in range(count):
            src = self.rng.choice(nodes)
            # Re-sample dst in O(1) expected time until dst != src, avoiding O(V) list allocations per flow.
            dst = self.rng.choice(nodes)
            while dst == src:
                dst = self.rng.choice(nodes)
            flows.append(self._create_flow(src, dst, tick, bytes_multiplier=bytes_mult))

        return flows
