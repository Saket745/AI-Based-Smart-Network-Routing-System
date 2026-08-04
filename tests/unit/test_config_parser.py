"""Unit tests for ConfigParser."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import yaml

from nroute.core.openconfig import (
    BGPConfig,
    BGPNeighborConfig,
    BGPSessionState,
    ConfigChange,
    DeviceConfig,
    InterfaceConfig,
    InterfaceState,
    OSPFConfig,
    OSPFInterfaceConfig,
)
from nroute.core.topology import Topology
from nroute.exceptions import IngestionError
from nroute.ingestion.config_parser import ConfigParser

if TYPE_CHECKING:
    from pathlib import Path


def test_load_device_configs_json_single(tmp_path: Path) -> None:
    """Test loading a single device config from JSON."""
    config_file = tmp_path / "device.json"
    data = {
        "hostname": "R1",
        "vendor": "cisco",
        "interfaces": [{"name": "GigabitEthernet0/1", "bandwidth": 1000.0}],
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    configs = ConfigParser.load_device_configs(config_file)
    assert len(configs) == 1
    assert configs[0].hostname == "R1"
    assert configs[0].vendor == "cisco"
    assert len(configs[0].interfaces) == 1
    assert configs[0].interfaces[0].name == "GigabitEthernet0/1"


def test_load_device_configs_yaml_list(tmp_path: Path) -> None:
    """Test loading a list of device configs from YAML."""
    config_file = tmp_path / "devices.yaml"
    data = [{"hostname": "R1", "vendor": "cisco"}, {"hostname": "R2", "vendor": "arista"}]
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

    configs = ConfigParser.load_device_configs(config_file)
    assert len(configs) == 2
    assert configs[0].hostname == "R1"
    assert configs[1].hostname == "R2"


def test_load_device_configs_devices_key(tmp_path: Path) -> None:
    """Test loading device configs from a top-level 'devices' key."""
    config_file = tmp_path / "config.json"
    data = {"devices": [{"hostname": "R1"}, {"hostname": "R2"}]}
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    configs = ConfigParser.load_device_configs(config_file)
    assert len(configs) == 2
    assert configs[0].hostname == "R1"
    assert configs[1].hostname == "R2"


def test_load_device_configs_not_found() -> None:
    """Test load_device_configs with non-existent file."""
    with pytest.raises(IngestionError, match="Config file not found"):
        ConfigParser.load_device_configs("non_existent.json")


def test_load_device_configs_unsupported_extension(tmp_path: Path) -> None:
    """Test load_device_configs with unsupported extension."""
    config_file = tmp_path / "device.txt"
    config_file.touch()
    with pytest.raises(IngestionError, match="Unsupported config file extension"):
        ConfigParser.load_device_configs(config_file)


def test_load_device_configs_malformed_json(tmp_path: Path) -> None:
    """Test load_device_configs with malformed JSON."""
    config_file = tmp_path / "bad.json"
    with open(config_file, "w", encoding="utf-8") as f:
        f.write("{invalid: json}")
    with pytest.raises(IngestionError, match="Failed to parse config file"):
        ConfigParser.load_device_configs(config_file)


def test_load_device_configs_invalid_structure(tmp_path: Path) -> None:
    """Test load_device_configs with invalid top-level structure."""
    config_file = tmp_path / "bad.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump("not a dict or list", f)
    with pytest.raises(
        IngestionError, match="must be a dict, list, or contain a top-level 'devices' key"
    ):
        ConfigParser.load_device_configs(config_file)


def test_load_device_configs_entry_not_dict(tmp_path: Path) -> None:
    """Test load_device_configs where an entry in the list is not a dict."""
    config_file = tmp_path / "bad.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump([{"hostname": "R1"}, "not a dict"], f)
    with pytest.raises(IngestionError, match=r"Config entry #1 in .* is not a dict"):
        ConfigParser.load_device_configs(config_file)


def test_load_device_configs_validation_failed(tmp_path: Path) -> None:
    """Test load_device_configs with validation failure."""
    config_file = tmp_path / "bad.json"
    # Missing required 'hostname'
    data = {"vendor": "cisco"}
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    with pytest.raises(IngestionError, match="validation failed"):
        ConfigParser.load_device_configs(config_file)


def test_load_change_valid(tmp_path: Path) -> None:
    """Test loading a valid ConfigChange."""
    change_file = tmp_path / "change.yaml"
    data = {
        "description": "Test change",
        "devices": [{"hostname": "R1", "vendor": "cisco"}],
        "node_changes": [{"id": "R2", "status": "down"}],
    }
    with open(change_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f)

    change = ConfigParser.load_change(change_file)
    assert change.description == "Test change"
    assert len(change.devices) == 1
    assert change.devices[0].hostname == "R1"
    assert len(change.node_changes) == 1
    assert change.node_changes[0]["id"] == "R2"


def test_load_change_not_found() -> None:
    """Test load_change with non-existent file."""
    with pytest.raises(IngestionError, match="Change file not found"):
        ConfigParser.load_change("non_existent.json")


def test_load_change_unsupported_extension(tmp_path: Path) -> None:
    """Test load_change with unsupported extension."""
    change_file = tmp_path / "change.txt"
    change_file.touch()
    with pytest.raises(IngestionError, match="Unsupported change file extension"):
        ConfigParser.load_change(change_file)


def test_load_change_malformed_yaml(tmp_path: Path) -> None:
    """Test load_change with malformed YAML."""
    change_file = tmp_path / "bad.yaml"
    with open(change_file, "w", encoding="utf-8") as f:
        f.write("invalid: : yaml")
    with pytest.raises(IngestionError, match="Failed to parse change file"):
        ConfigParser.load_change(change_file)


def test_load_change_not_a_dict(tmp_path: Path) -> None:
    """Test load_change with non-dict structure."""
    change_file = tmp_path / "bad.json"
    with open(change_file, "w", encoding="utf-8") as f:
        json.dump([1, 2, 3], f)
    with pytest.raises(IngestionError, match="Change file must contain a single JSON/YAML object"):
        ConfigParser.load_change(change_file)


def test_load_change_validation_failed(tmp_path: Path) -> None:
    """Test load_change with validation failure."""
    change_file = tmp_path / "bad.json"
    # devices should be a list of DeviceConfig
    data = {"devices": "not a list"}
    with open(change_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    with pytest.raises(IngestionError, match="Change file validation failed"):
        ConfigParser.load_change(change_file)


def test_apply_device_configs() -> None:
    """Test applying device configurations to a topology."""
    topo = Topology()
    topo.add_node("R1")
    topo.add_node("R2")
    topo.add_edge("R1", "R2", interface="Gig0/1")

    configs = [
        DeviceConfig(
            hostname="R1",
            metadata={"custom_attr": "value"},
            interfaces=[
                InterfaceConfig(name="Gig0/1", state=InterfaceState.DOWN, bandwidth=2000.0)
            ],
        ),
        DeviceConfig(hostname="R3", metadata={"role": "router", "custom_attr": "value2"}),
    ]

    # Test applying configs, including creating missing node R3
    ConfigParser.apply_device_configs(topo, configs, create_missing_nodes=True)

    assert "R3" in topo.nodes
    assert topo.get_node("R1")["custom_attr"] == "value"
    assert topo.get_node("R3")["custom_attr"] == "value2"
    assert topo.get_node("R3")["type"] == "router"

    # Check that R1-R2 link is now down and bandwidth updated
    assert topo.get_edge("R1", "R2")["status"] == "down"
    assert topo.get_edge("R1", "R2")["bandwidth"] == 2000.0

    # Test interface state UP and capacity derivation
    configs2 = [
        DeviceConfig(
            hostname="R1",
            interfaces=[InterfaceConfig(name="Gig0/1", state=InterfaceState.UP, bandwidth=3000.0)],
        )
    ]
    ConfigParser.apply_device_configs(topo, configs2)
    assert topo.get_edge("R1", "R2")["status"] == "up"
    assert topo.get_edge("R1", "R2")["bandwidth"] == 3000.0
    assert topo.get_node("R1")["capacity"] == 3000.0


def test_apply_device_configs_no_create() -> None:
    """Test apply_device_configs with create_missing_nodes=False."""
    topo = Topology()
    topo.add_node("R1")

    configs = [
        DeviceConfig(hostname="R1", metadata={"role": "core"}),
        DeviceConfig(hostname="R2", metadata={"role": "edge"}),
    ]

    ConfigParser.apply_device_configs(topo, configs, create_missing_nodes=False)

    assert "R2" not in topo.nodes
    assert topo.get_node("R1")["role"] == "core"


def test_apply_change() -> None:
    """Test applying a ConfigChange to a topology."""
    topo = Topology()
    topo.add_node("R1", status="up")
    topo.add_node("R2", status="up")
    topo.add_edge("R1", "R2", status="up")

    # Add a node that will be set to 'up'
    topo.add_node("R3", status="down")

    change = ConfigChange(
        description="Complex change",
        devices=[DeviceConfig(hostname="R1", metadata={"vendor": "cisco"})],
        node_changes=[
            {"id": "R2", "status": "down"},
            {"id": "R3", "status": "up"},
            {"hostname": "R1", "status": "up"},
            {"id": "MISSING_NODE", "status": "down"},
            {"something": "else"},
        ],
        link_changes=[
            {"src": "R1", "dst": "R2", "bandwidth": 5000.0},
            {"src": "R1", "dst": "MISSING_NODE", "status": "down"},
            {"src": "R1"},
        ],
    )

    new_topo = ConfigParser.apply_change(topo, change)

    # Original topo should be unchanged (it uses a copy)
    assert topo.get_node("R2")["status"] == "up"
    assert topo.get_edge("R1", "R2")["status"] == "up"

    # New topo should have changes
    assert new_topo.get_node("R1")["vendor"] == "cisco"
    assert new_topo.get_node("R2")["status"] == "down"
    assert new_topo.get_node("R3")["status"] == "up"
    assert new_topo.get_edge("R1", "R2")["bandwidth"] == 5000.0


def test_apply_ospf_and_bgp() -> None:
    """Test applying OSPF and BGP configurations."""
    topo = Topology()
    topo.add_node("R1")
    topo.add_node("R2")
    topo.add_edge("R1", "R2", interface="Gig0/1")

    config = DeviceConfig(
        hostname="R1",
        ospf=OSPFConfig(
            interfaces=[OSPFInterfaceConfig(interface_name="Gig0/1", cost=50, area="0.0.0.1")]
        ),
        bgp=BGPConfig(
            local_as=65001,
            neighbors=[
                BGPNeighborConfig(
                    neighbor_address="R2", remote_as=65002, state=BGPSessionState.ESTABLISHED
                )
            ],
        ),
    )

    ConfigParser.apply_device_configs(topo, [config])

    edge = topo.get_edge("R1", "R2")
    assert edge["weight"] == 50.0
    assert edge["ospf_cost"] == 50
    assert edge["ospf_area"] == "0.0.0.1"
    assert edge["bgp_local_as"] == 65001
    assert edge["bgp_remote_as"] == 65002
    assert edge["bgp_state"] == "established"
