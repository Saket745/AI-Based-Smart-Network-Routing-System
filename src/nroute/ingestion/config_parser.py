"""Canonical Network Model configuration parser.

Ingests YAML / JSON device configurations conforming to the OpenConfig-inspired
schemas defined in ``nroute.core.openconfig`` and translates them into
``Topology`` node/edge attribute updates.

Phase 1 supports structured inputs only (YAML, JSON, OpenConfig JSON/YAML).
Vendor-specific CLI config parsers (Cisco IOS, Arista EOS, Juniper JunOS)
are planned for Phase 2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from nroute.core.openconfig import ConfigChange, DeviceConfig
from nroute.exceptions import IngestionError
from nroute.utils.logging import get_logger

if TYPE_CHECKING:
    from nroute.core.topology import Topology

logger = get_logger(__name__)


class ConfigParser:
    """Translates Canonical Network Model YAML/JSON configs into Topology mutations."""

    # ── Loading helpers ──────────────────────────────────────

    @staticmethod
    def load_device_configs(path: str | Path) -> list[DeviceConfig]:
        """Load one or more device configurations from a YAML or JSON file.

        The file may contain:
        * A single device config object.
        * A list of device config objects.
        * A top-level key ``devices`` containing a list.

        Returns:
            List of validated ``DeviceConfig`` instances.
        """
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"Config file not found: {path}")

        try:
            with open(p, encoding="utf-8") as f:
                if p.suffix.lower() in {".yaml", ".yml"}:
                    raw = yaml.safe_load(f)
                elif p.suffix.lower() == ".json":
                    raw = json.load(f)
                else:
                    raise IngestionError(
                        f"Unsupported config file extension '{p.suffix}'. "
                        "Use .yaml, .yml, or .json."
                    )
        except (yaml.YAMLError, json.JSONDecodeError) as exc:
            raise IngestionError(f"Failed to parse config file {path}: {exc}") from exc

        return ConfigParser._parse_raw(raw, str(path))

    @staticmethod
    def load_change(path: str | Path) -> ConfigChange:
        """Load a ``ConfigChange`` patch from a YAML or JSON file.

        The file must conform to the ``ConfigChange`` Pydantic schema.
        """
        p = Path(path)
        if not p.is_file():
            raise IngestionError(f"Change file not found: {path}")

        try:
            with open(p, encoding="utf-8") as f:
                if p.suffix.lower() in {".yaml", ".yml"}:
                    raw = yaml.safe_load(f)
                elif p.suffix.lower() == ".json":
                    raw = json.load(f)
                else:
                    raise IngestionError(
                        f"Unsupported change file extension '{p.suffix}'. "
                        "Use .yaml, .yml, or .json."
                    )
        except (yaml.YAMLError, json.JSONDecodeError) as exc:
            raise IngestionError(f"Failed to parse change file {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise IngestionError("Change file must contain a single JSON/YAML object.")

        try:
            return ConfigChange.model_validate(raw)
        except Exception as exc:
            raise IngestionError(f"Change file validation failed: {exc}") from exc

    # ── Topology translation ─────────────────────────────────

    @staticmethod
    def apply_device_configs(
        topology: Topology,
        configs: list[DeviceConfig],
        *,
        create_missing_nodes: bool = True,
    ) -> Topology:
        """Apply a list of device configs to a topology (in-place).

        For each device:
        * Ensures the node exists (creates it if ``create_missing_nodes``).
        * Updates node attributes from the config (status, capacity, metadata).
        * Updates OSPF costs on edges whose interface names match.
        * Creates edges implied by BGP peerings if both peers exist.

        Args:
            topology: The topology to mutate.
            configs: Device configurations to apply.
            create_missing_nodes: If True, add nodes that don't yet exist.

        Returns:
            The mutated topology (same object, for chaining).
        """
        for dev in configs:
            node_id = dev.hostname

            # Ensure node exists
            if node_id not in topology.nodes:
                if create_missing_nodes:
                    topology.add_node(
                        node_id,
                        type=dev.metadata.get("role", "router"),
                        status="up",
                    )
                    logger.info("Created node from config", node_id=node_id)
                else:
                    logger.warning(
                        "Node not in topology, skipping",
                        node_id=node_id,
                    )
                    continue

            # Update node-level attributes
            node_updates: dict[str, Any] = {}
            if dev.metadata:
                for k, v in dev.metadata.items():
                    node_updates[k] = v

            # Derive aggregate bandwidth from interfaces
            iface_bw = [
                iface.bandwidth for iface in dev.interfaces if iface.state.value == "up"
            ]
            if iface_bw:
                node_updates["capacity"] = max(iface_bw)

            if node_updates:
                topology.get_node(node_id)
                # Only update extra/custom attrs — avoid overwriting validated fields
                for k, v in node_updates.items():
                    topology._graph.nodes[node_id][k] = v

            # Apply interface states to edges
            for iface in dev.interfaces:
                ConfigParser._apply_interface(topology, node_id, iface)

            # Apply OSPF costs to edges
            if dev.ospf:
                ConfigParser._apply_ospf(topology, node_id, dev.ospf)

            # Apply BGP peerings (informational edge metadata)
            if dev.bgp:
                ConfigParser._apply_bgp(topology, node_id, dev.bgp)

        return topology

    @staticmethod
    def apply_change(topology: Topology, change: ConfigChange) -> Topology:
        """Apply a ``ConfigChange`` patch to a topology copy.

        This does NOT mutate the original — it operates on a deep copy.

        Returns:
            A new ``Topology`` representing the post-change state.
        """
        modified = topology.copy()

        # 1. Apply device config overrides
        if change.devices:
            ConfigParser.apply_device_configs(modified, change.devices)

        # 2. Apply explicit node-level overrides
        for node_change in change.node_changes:
            nid = node_change.get("id") or node_change.get("hostname")
            if nid is None:
                continue
            if nid not in modified.nodes:
                logger.warning("Node change target missing", node_id=nid)
                continue
            status = node_change.get("status")
            if status == "down":
                modified.set_node_down(nid)
            elif status == "up":
                modified.set_node_up(nid)

        # 3. Apply explicit link-level overrides
        for link_change in change.link_changes:
            src = link_change.get("src") or link_change.get("source")
            dst = link_change.get("dst") or link_change.get("target")
            if not src or not dst:
                continue
            if (src, dst) not in modified.edges:
                logger.warning("Link change target missing", src=src, dst=dst)
                continue
            update_attrs = {
                k: v
                for k, v in link_change.items()
                if k not in {"src", "dst", "source", "target"}
            }
            if update_attrs:
                modified.update_edge(src, dst, **update_attrs)

        return modified

    # ── Private helpers ──────────────────────────────────────

    @staticmethod
    def _parse_raw(raw: Any, source: str) -> list[DeviceConfig]:
        """Convert raw parsed YAML/JSON into validated DeviceConfig list."""
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("devices", [raw])
        else:
            raise IngestionError(
                f"Config file {source} must be a dict, list, or contain a top-level 'devices' key."
            )

        configs: list[DeviceConfig] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise IngestionError(f"Config entry #{idx} in {source} is not a dict.")
            try:
                configs.append(DeviceConfig.model_validate(item))
            except Exception as exc:
                raise IngestionError(
                    f"Config entry #{idx} in {source} validation failed: {exc}"
                ) from exc

        return configs

    @staticmethod
    def _apply_interface(
        topology: Topology,
        node_id: str,
        iface: Any,
    ) -> None:
        """Apply interface state to matching edges."""
        from nroute.core.openconfig import InterfaceConfig

        iface: InterfaceConfig  # type: ignore[no-redef]

        # Walk outgoing edges and update those whose stored interface name matches
        for neighbor in list(topology.neighbors(node_id)):
            edge = topology.get_edge(node_id, neighbor)
            edge_iface = edge.get("interface", "")
            if edge_iface == iface.name:
                if iface.state.value == "down":
                    topology.set_link_down(node_id, neighbor)
                elif iface.state.value == "up":
                    topology.set_link_up(node_id, neighbor)
                if iface.bandwidth > 0:
                    topology.update_edge(node_id, neighbor, bandwidth=iface.bandwidth)

    @staticmethod
    def _apply_ospf(topology: Topology, node_id: str, ospf: Any) -> None:
        """Apply OSPF cost metrics to edges."""
        from nroute.core.openconfig import OSPFConfig

        ospf: OSPFConfig  # type: ignore[no-redef]

        for ospf_iface in ospf.interfaces:
            for neighbor in list(topology.neighbors(node_id)):
                edge = topology.get_edge(node_id, neighbor)
                edge_iface = edge.get("interface", "")
                if edge_iface == ospf_iface.interface_name:
                    topology.update_edge(
                        node_id,
                        neighbor,
                        weight=float(ospf_iface.cost),
                        ospf_area=ospf_iface.area,
                        ospf_cost=ospf_iface.cost,
                    )

    @staticmethod
    def _apply_bgp(topology: Topology, node_id: str, bgp: Any) -> None:
        """Store BGP peering metadata on edges."""
        from nroute.core.openconfig import BGPConfig

        bgp: BGPConfig  # type: ignore[no-redef]

        for peer in bgp.neighbors:
            peer_id = peer.neighbor_address
            if peer_id in topology.nodes and (node_id, peer_id) in topology.edges:
                topology.update_edge(
                    node_id,
                    peer_id,
                    bgp_remote_as=peer.remote_as,
                    bgp_local_as=bgp.local_as,
                    bgp_state=peer.state.value,
                )
