"""Vendor-neutral Canonical Network Model schemas based on OpenConfig.

Defines Pydantic models for representing network device configurations
in a normalized, vendor-agnostic format.  Phase 1 accepts YAML/JSON inputs
conforming to these schemas; vendor-specific CLI parsers are deferred to
Phase 2.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ── Enums ────────────────────────────────────────────────────


class InterfaceState(str, Enum):
    """Administrative / operational interface state."""

    UP = "up"
    DOWN = "down"
    TESTING = "testing"


class OSPFNetworkType(str, Enum):
    """OSPF network type on an interface."""

    BROADCAST = "broadcast"
    POINT_TO_POINT = "point-to-point"
    NBMA = "nbma"


class BGPSessionState(str, Enum):
    """BGP neighbor session state (simplified)."""

    IDLE = "idle"
    CONNECT = "connect"
    ACTIVE = "active"
    OPEN_SENT = "open-sent"
    OPEN_CONFIRM = "open-confirm"
    ESTABLISHED = "established"


# ── Interface Models ─────────────────────────────────────────


class InterfaceConfig(BaseModel):
    """openconfig-interfaces inspired interface configuration."""

    name: str = Field(..., description="Interface name, e.g. 'GigabitEthernet0/1'")
    description: str = Field(default="", description="Human-readable description")
    state: InterfaceState = Field(default=InterfaceState.UP)
    bandwidth: float = Field(
        default=1000.0,
        ge=0,
        description="Interface bandwidth in Mbps",
    )
    mtu: int = Field(
        default=1500, ge=68, le=9216, description="Maximum transmission unit"
    )
    ipv4_address: str | None = Field(
        default=None, description="IPv4 address in CIDR notation"
    )
    ipv6_address: str | None = Field(
        default=None, description="IPv6 address in CIDR notation"
    )
    vlan_id: int | None = Field(default=None, ge=1, le=4094, description="VLAN tag")


# ── OSPF Models ──────────────────────────────────────────────


class OSPFInterfaceConfig(BaseModel):
    """OSPF parameters for a single interface."""

    interface_name: str = Field(..., description="Interface to which OSPF binds")
    cost: int = Field(default=10, ge=1, le=65535, description="OSPF cost metric")
    area: str = Field(default="0.0.0.0", description="OSPF area ID")
    passive: bool = Field(default=False, description="Passive interface flag")
    network_type: OSPFNetworkType = Field(default=OSPFNetworkType.BROADCAST)
    hello_interval: int = Field(
        default=10, ge=1, description="Hello interval in seconds"
    )
    dead_interval: int = Field(default=40, ge=1, description="Dead interval in seconds")


class OSPFConfig(BaseModel):
    """Top-level OSPF process configuration."""

    router_id: str | None = Field(default=None, description="OSPF router-id")
    process_id: int = Field(default=1, ge=1, description="OSPF process ID")
    interfaces: list[OSPFInterfaceConfig] = Field(default_factory=list)
    redistribute: list[str] = Field(
        default_factory=list,
        description="Protocols to redistribute into OSPF, e.g. ['bgp', 'static']",
    )


# ── BGP Models ───────────────────────────────────────────────


class BGPNeighborConfig(BaseModel):
    """BGP neighbor / peer configuration."""

    neighbor_address: str = Field(..., description="Peer IPv4/IPv6 address")
    remote_as: int = Field(..., ge=1, le=4294967295, description="Remote AS number")
    description: str = Field(default="")
    state: BGPSessionState = Field(default=BGPSessionState.ESTABLISHED)
    import_policy: str | None = Field(
        default=None, description="Inbound route-policy name"
    )
    export_policy: str | None = Field(
        default=None, description="Outbound route-policy name"
    )
    multihop_ttl: int | None = Field(default=None, ge=1, le=255)


class BGPConfig(BaseModel):
    """Top-level BGP configuration."""

    local_as: int = Field(..., ge=1, le=4294967295, description="Local AS number")
    router_id: str | None = Field(default=None, description="BGP router-id")
    neighbors: list[BGPNeighborConfig] = Field(default_factory=list)
    networks: list[str] = Field(
        default_factory=list,
        description="Networks to originate, e.g. ['10.0.0.0/8']",
    )


# ── Static Route Models ─────────────────────────────────────


class StaticRoute(BaseModel):
    """A single static route entry."""

    prefix: str = Field(..., description="Destination prefix in CIDR notation")
    next_hop: str = Field(..., description="Next-hop IP address or interface name")
    metric: int = Field(default=1, ge=0, description="Administrative distance / metric")


# ── ACL / Policy Models ─────────────────────────────────────


class ACLEntry(BaseModel):
    """A single access-control list entry (simplified)."""

    sequence: int = Field(..., ge=1, description="Sequence number")
    action: str = Field(..., description="permit | deny")
    protocol: str = Field(default="ip", description="Protocol: ip | tcp | udp | icmp")
    source: str = Field(default="any", description="Source prefix or 'any'")
    destination: str = Field(default="any", description="Destination prefix or 'any'")
    dst_port: int | None = Field(default=None, ge=0, le=65535)


class ACLConfig(BaseModel):
    """Named access-control list."""

    name: str = Field(..., description="ACL name")
    entries: list[ACLEntry] = Field(default_factory=list)


# ── Device Configuration (top-level) ────────────────────────


class DeviceConfig(BaseModel):
    """Full canonical device configuration for a single network device.

    This is the normalised representation the Digital Twin Engine consumes.
    """

    hostname: str = Field(..., description="Device hostname / node-id")
    vendor: str = Field(
        default="generic", description="Vendor hint (cisco, arista, juniper, generic)"
    )
    interfaces: list[InterfaceConfig] = Field(default_factory=list)
    ospf: OSPFConfig | None = Field(default=None)
    bgp: BGPConfig | None = Field(default=None)
    static_routes: list[StaticRoute] = Field(default_factory=list)
    acls: list[ACLConfig] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata (location, role, etc.)",
    )


# ── Config Change Patch ──────────────────────────────────────


class ConfigChange(BaseModel):
    """Represents a proposed configuration change to be simulated.

    The Digital Twin applies these changes to its topology copy and
    compares the resulting routing / reachability state against the
    baseline.
    """

    description: str = Field(
        default="", description="Human-readable change description"
    )
    devices: list[DeviceConfig] = Field(
        default_factory=list,
        description="Full or partial device configs representing the desired post-change state",
    )
    link_changes: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Edge-level overrides: [{'src': 'R1', 'dst': 'R2', 'status': 'down'}, ...]"
        ),
    )
    node_changes: list[dict[str, Any]] = Field(
        default_factory=list,
        description=("Node-level overrides: [{'id': 'R3', 'status': 'down'}, ...]"),
    )
