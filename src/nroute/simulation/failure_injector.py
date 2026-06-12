"""Failure injector for scheduling and applying network failures and recovery events."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from nroute.utils.logging import get_logger

if TYPE_CHECKING:
    from nroute.core.topology import Topology

logger = get_logger(__name__)


class FailureInjector:
    """
    Schedules and applies link/node failures, recoveries, and latency spikes.
    """

    def __init__(self) -> None:
        # Maps tick -> list of event dicts
        self.events: dict[int, list[dict[str, Any]]] = defaultdict(list)
        # Tracks original values for temporary modifications (e.g. latency spikes)
        # Key: (src, dst), Value: original_latency
        self._original_latencies: dict[tuple[str, str], float] = {}

    def schedule_link_failure(self, src: str, dst: str, tick: int) -> None:
        """Schedule a link failure event."""
        self.events[tick].append({
            "type": "link_failure",
            "src": src,
            "dst": dst,
        })

    def schedule_node_failure(self, node_id: str, tick: int) -> None:
        """Schedule a node failure event."""
        self.events[tick].append({
            "type": "node_failure",
            "node_id": node_id,
        })

    def schedule_recovery(self, src: str, dst: str, tick: int) -> None:
        """Schedule a link recovery event."""
        self.events[tick].append({
            "type": "link_recovery",
            "src": src,
            "dst": dst,
        })

    def schedule_node_recovery(self, node_id: str, tick: int) -> None:
        """Schedule a node recovery event."""
        self.events[tick].append({
            "type": "node_recovery",
            "node_id": node_id,
        })

    def schedule_latency_spike(
        self, src: str, dst: str, tick: int, multiplier: float, duration_ticks: int
    ) -> None:
        """
        Schedule a temporary latency spike on a link.
        """
        self.events[tick].append({
            "type": "latency_spike",
            "src": src,
            "dst": dst,
            "multiplier": multiplier,
            "duration": duration_ticks,
        })

    def apply(self, topology: Topology, current_tick: int) -> None:
        """
        Apply all scheduled events for the current tick to the topology.

        Args:
            topology: The network topology.
            current_tick: The current simulation tick index.
        """
        # 1. Apply events scheduled for this tick
        if current_tick in self.events:
            for event in self.events[current_tick]:
                evt_type = event["type"]
                
                if evt_type == "link_failure":
                    src, dst = event["src"], event["dst"]
                    try:
                        topology.set_link_down(src, dst)
                        logger.info("Applied link failure event", src=src, dst=dst, tick=current_tick)
                    except Exception as e:
                        logger.error("Failed to apply link failure", src=src, dst=dst, error=str(e))
                        
                elif evt_type == "node_failure":
                    node_id = event["node_id"]
                    try:
                        topology.set_node_down(node_id)
                        logger.info("Applied node failure event", node_id=node_id, tick=current_tick)
                    except Exception as e:
                        logger.error("Failed to apply node failure", node_id=node_id, error=str(e))
                        
                elif evt_type == "link_recovery":
                    src, dst = event["src"], event["dst"]
                    try:
                        topology.set_link_up(src, dst)
                        logger.info("Applied link recovery event", src=src, dst=dst, tick=current_tick)
                    except Exception as e:
                        logger.error("Failed to apply link recovery", src=src, dst=dst, error=str(e))

                elif evt_type == "node_recovery":
                    node_id = event["node_id"]
                    try:
                        topology.set_node_up(node_id)
                        logger.info("Applied node recovery event", node_id=node_id, tick=current_tick)
                    except Exception as e:
                        logger.error("Failed to apply node recovery", node_id=node_id, error=str(e))
                        
                elif evt_type == "latency_spike":
                    src, dst = event["src"], event["dst"]
                    mult = event["multiplier"]
                    dur = event["duration"]
                    try:
                        edge_data = topology.get_edge(src, dst)
                        orig_lat = float(edge_data.get("latency", 5.0))
                        
                        # Store original latency if not already tracked
                        key = (src, dst)
                        if key not in self._original_latencies:
                            self._original_latencies[key] = orig_lat
                            
                        new_lat = orig_lat * mult
                        topology.update_edge(src, dst, latency=new_lat)
                        logger.info(
                            "Applied latency spike event",
                            src=src,
                            dst=dst,
                            old_latency=orig_lat,
                            new_latency=new_lat,
                            tick=current_tick,
                        )
                        
                        # Schedule recovery
                        restore_tick = current_tick + dur
                        self.events[restore_tick].append({
                            "type": "restore_latency",
                            "src": src,
                            "dst": dst,
                        })
                    except Exception as e:
                        logger.error("Failed to apply latency spike", src=src, dst=dst, error=str(e))

                elif evt_type == "restore_latency":
                    src, dst = event["src"], event["dst"]
                    key = (src, dst)
                    if key in self._original_latencies:
                        orig_lat = self._original_latencies.pop(key)
                        try:
                            topology.update_edge(src, dst, latency=orig_lat)
                            logger.info(
                                "Restored latency after spike",
                                src=src,
                                dst=dst,
                                latency=orig_lat,
                                tick=current_tick,
                            )
                        except Exception as e:
                            logger.error("Failed to restore latency", src=src, dst=dst, error=str(e))
