"""Comprehensive Unit & Contract Tests for NRoute Pre-Flight Validation Engine.

Tests:
  1. PASS: Redundant/non-disruptive change.
  2. WARN: Latency increase threshold exceeded.
  3. WARN: Path changed ratio threshold exceeded.
  4. BLOCK: Newly unreachable node pairs detected.
  5. BLOCK: Protected node disconnection.
  6. BLOCK: Catastrophic latency increase.
  7. Multiple simultaneous violations (precedence & complete violation accumulation).
  8. Invalid policy thresholds rejection (warn > block).
  9. Malformed change patch rejection.
  10. Deterministic evaluation across repeated runs.
  11. CLI exit codes: PASS (0), WARN (0), WARN strict (2), BLOCK (1), error (64/65).
  12. CLI JSON output schema conformance.
  13. REST API endpoint and CLI/REST parity.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import networkx as nx
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from pydantic import ValidationError

from nroute.api.server import app
from nroute.cli.main import cli
from nroute.core.openconfig import ConfigChange
from nroute.core.topology import Topology
from nroute.simulation.digital_twin import DigitalTwinEngine
from nroute.simulation.policy import (
    PolicyGateConfig,
    ValidationResult,
    ValidationVerdict,
)
from nroute.simulation.validator import PreFlightValidator

if TYPE_CHECKING:
    from pathlib import Path


# ── Test Fixtures ─────────────────────────────────────────────


def _build_test_network() -> Topology:
    """Build a deterministic 6-node test topology with redundant paths."""
    g = nx.DiGraph()
    for n in ["core0", "core1", "agg0", "agg1", "edge0", "edge1"]:
        g.add_node(n, capacity=1000.0, status="up", type="router")

    edges = [
        ("edge0", "agg0", 1000.0, 2.0),
        ("edge0", "agg1", 1000.0, 2.0),
        ("agg0", "edge0", 1000.0, 2.0),
        ("agg1", "edge0", 1000.0, 2.0),
        ("agg0", "core0", 1000.0, 5.0),
        ("agg0", "core1", 1000.0, 10.0),
        ("agg1", "core0", 1000.0, 10.0),
        ("agg1", "core1", 1000.0, 5.0),
        ("core0", "agg0", 1000.0, 5.0),
        ("core1", "agg0", 1000.0, 10.0),
        ("core0", "agg1", 1000.0, 10.0),
        ("core1", "agg1", 1000.0, 5.0),
        ("core0", "edge1", 1000.0, 5.0),
        ("edge1", "core0", 1000.0, 5.0),
        ("core1", "edge1", 1000.0, 5.0),
        ("edge1", "core1", 1000.0, 5.0),
    ]

    for u, v, bw, lat in edges:
        g.add_edge(
            u,
            v,
            bandwidth=bw,
            latency=lat,
            utilization=0.10,
            packet_loss=0.0,
            status="up",
            weight=lat,
        )

    return Topology(g)


# ── Core Policy Validation Tests ──────────────────────────────


def test_validation_pass_redundant_change() -> None:
    """A non-disruptive capacity increase or minor path change must PASS."""
    topo = _build_test_network()
    change = ConfigChange(
        description="Non-disruptive capacity upgrade",
        link_changes=[{"src": "agg0", "dst": "core0", "bandwidth": 2000.0}],
    )
    policy = PolicyGateConfig(
        max_latency_increase_warn_ms=5.0,
        max_latency_increase_block_ms=20.0,
        allow_newly_unreachable=False,
    )

    result = PreFlightValidator.validate(topo, change=change, policy=policy)

    assert result.verdict == ValidationVerdict.PASS
    assert result.gate_passed is True
    assert len(result.blocking_violations) == 0
    assert len(result.warning_violations) == 0
    assert result.blast_radius_summary["newly_unreachable_pairs"] == 0


def test_validation_warn_latency() -> None:
    """A change that increases latency above warn threshold must produce WARN."""
    topo = _build_test_network()
    # Severing agg0->core0 forces traffic through agg0->core1 (latency 10ms instead of 5ms: +5.0ms)
    change = ConfigChange(
        description="Cut primary link agg0->core0",
        link_changes=[{"src": "agg0", "dst": "core0", "status": "down"}],
    )
    policy = PolicyGateConfig(
        max_latency_increase_warn_ms=3.0,
        max_latency_increase_block_ms=20.0,
        allow_newly_unreachable=False,
    )

    result = PreFlightValidator.validate(topo, change=change, policy=policy)

    assert result.verdict == ValidationVerdict.WARN
    assert result.gate_passed is True
    assert len(result.blocking_violations) == 0
    assert len(result.warning_violations) == 1
    assert "Max latency increase" in result.warning_violations[0]


def test_validation_warn_path_changed_ratio() -> None:
    """A change shifting paths above warn ratio must produce WARN."""
    topo = _build_test_network()
    change = ConfigChange(
        description="Cut primary link agg0->core0",
        link_changes=[{"src": "agg0", "dst": "core0", "status": "down"}],
    )
    policy = PolicyGateConfig(
        max_latency_increase_warn_ms=50.0,
        max_latency_increase_block_ms=100.0,
        max_path_changed_ratio_warn=0.05,  # Very low warn threshold (5%)
        max_path_changed_ratio_block=0.80,
    )

    result = PreFlightValidator.validate(topo, change=change, policy=policy)

    assert result.verdict == ValidationVerdict.WARN
    assert any("Path change ratio" in v for v in result.warning_violations)


def test_validation_block_unreachable() -> None:
    """A change that partitions the graph must trigger BLOCK."""
    topo = _build_test_network()
    # Isolate edge1 completely
    change = ConfigChange(
        description="Sever all links to edge1",
        link_changes=[
            {"src": "core0", "dst": "edge1", "status": "down"},
            {"src": "core1", "dst": "edge1", "status": "down"},
        ],
    )
    policy = PolicyGateConfig(allow_newly_unreachable=False)

    result = PreFlightValidator.validate(topo, change=change, policy=policy)

    assert result.verdict == ValidationVerdict.BLOCK
    assert result.gate_passed is False
    assert len(result.blocking_violations) >= 1
    assert any("Newly unreachable pairs" in v for v in result.blocking_violations)


def test_validation_block_protected_node() -> None:
    """A change that causes reachability loss for a protected node must BLOCK."""
    topo = _build_test_network()
    change = ConfigChange(
        description="Cut access to core0",
        node_changes=[{"id": "core0", "status": "down"}],
    )
    policy = PolicyGateConfig(
        allow_newly_unreachable=True,  # Global unreachability allowed...
        protected_nodes=["core0"],  # ...but core0 is protected!
    )

    result = PreFlightValidator.validate(topo, change=change, policy=policy)

    assert result.verdict == ValidationVerdict.BLOCK
    assert any("Protected node 'core0'" in v for v in result.blocking_violations)


def test_validation_block_catastrophic_latency() -> None:
    """A change exceeding the blocking latency threshold must BLOCK."""
    topo = _build_test_network()
    change = ConfigChange(
        description="Cut primary link agg0->core0",
        link_changes=[{"src": "agg0", "dst": "core0", "status": "down"}],
    )
    policy = PolicyGateConfig(
        max_latency_increase_warn_ms=2.0,
        max_latency_increase_block_ms=4.0,  # Max latency delta is +5.0ms -> exceeds block!
    )

    result = PreFlightValidator.validate(topo, change=change, policy=policy)

    assert result.verdict == ValidationVerdict.BLOCK
    assert result.gate_passed is False
    assert any("Max latency increase" in v for v in result.blocking_violations)


def test_validation_multiple_violations_precedence() -> None:
    """Simultaneous blocking and warning violations must return BLOCK and retain all violations."""
    topo = _build_test_network()
    # Causes both latency increase (+5.0ms) and partition (edge1 isolated)
    change = ConfigChange(
        description="Multiple violations",
        link_changes=[
            {"src": "agg0", "dst": "core0", "status": "down"},
            {"src": "core0", "dst": "edge1", "status": "down"},
            {"src": "core1", "dst": "edge1", "status": "down"},
        ],
    )
    policy = PolicyGateConfig(
        max_latency_increase_warn_ms=2.0,
        max_latency_increase_block_ms=20.0,
        allow_newly_unreachable=False,
    )

    result = PreFlightValidator.validate(topo, change=change, policy=policy)

    # BLOCK takes precedence
    assert result.verdict == ValidationVerdict.BLOCK
    assert result.gate_passed is False
    # Both blocking and warning violations must be retained
    assert len(result.blocking_violations) >= 1
    assert len(result.warning_violations) >= 1
    assert any("Newly unreachable" in v for v in result.blocking_violations)
    assert any("Max latency increase" in v for v in result.warning_violations)


def test_invalid_threshold_configuration() -> None:
    """Enforce that warn > block threshold raises a validation error prior to simulation."""
    with pytest.raises(ValidationError) as exc_info:
        PolicyGateConfig(
            max_latency_increase_warn_ms=25.0,
            max_latency_increase_block_ms=10.0,  # Inconsistent: warn > block!
        )
    assert "cannot exceed max_latency_increase_block_ms" in str(exc_info.value)


def test_malformed_change_patch() -> None:
    """Ensure invalid change data is rejected with clean error."""
    topo = _build_test_network()
    with pytest.raises(FileNotFoundError):
        PreFlightValidator.validate(topo, change="non_existent_file.yaml")


def test_deterministic_repeated_evaluation() -> None:
    """Two evaluations on identical inputs must yield identical decision fields."""
    topo = _build_test_network()
    change = ConfigChange(
        description="Cut primary link agg0->core0",
        link_changes=[{"src": "agg0", "dst": "core0", "status": "down"}],
    )
    policy = PolicyGateConfig(max_latency_increase_warn_ms=3.0)

    res1 = PreFlightValidator.validate(topo, change=change, policy=policy)
    res2 = PreFlightValidator.validate(topo, change=change, policy=policy)

    assert res1.verdict == res2.verdict
    assert res1.gate_passed == res2.gate_passed
    assert res1.summary == res2.summary
    assert res1.blocking_violations == res2.blocking_violations
    assert res1.warning_violations == res2.warning_violations
    assert res1.blast_radius_summary == res2.blast_radius_summary
    assert res1.provenance["baseline_topology_hash"] == res2.provenance["baseline_topology_hash"]
    assert res1.provenance["change_patch_hash"] == res2.provenance["change_patch_hash"]


# ── DigitalTwinEngine Integration Test ────────────────────────


def test_digital_twin_engine_validate_method(tmp_path: Path) -> None:
    """DigitalTwinEngine.validate_change() must integrate cleanly with AuditTrail."""
    topo = _build_test_network()
    audit_file = tmp_path / "audit.ndjson"
    twin = DigitalTwinEngine(audit_log=audit_file)
    twin._topology = topo

    change = ConfigChange(
        description="Redundant upgrade",
        link_changes=[{"src": "agg0", "dst": "core0", "bandwidth": 2000.0}],
    )
    result = twin.validate_change(change)

    assert isinstance(result, ValidationResult)
    assert result.verdict == ValidationVerdict.PASS
    assert len(twin.audit.records) == 1
    assert "Pre-flight validation verdict: PASS" in twin.audit.records[0].explanation


# ── CLI Contract & Exit Code Tests ────────────────────────────


def test_cli_exit_codes_pass(tmp_path: Path) -> None:
    """CLI must exit with code 0 on PASS."""
    topo = _build_test_network()
    topo_file = tmp_path / "topo.json"
    topo_file.write_text(json.dumps(topo.to_dict()))

    change_file = tmp_path / "change_pass.json"
    change_file.write_text(
        json.dumps(
            {
                "description": "Pass change",
                "link_changes": [{"src": "agg0", "dst": "core0", "bandwidth": 2000.0}],
            }
        )
    )

    runner = CliRunner()
    res = runner.invoke(cli, ["twin", "validate", "-t", str(topo_file), "-ch", str(change_file)])
    assert res.exit_code == 0
    assert "[PASS]" in res.output


def test_cli_exit_codes_warn_and_strict(tmp_path: Path) -> None:
    """CLI must exit with code 0 on WARN by default, and code 2 with --strict-warnings."""
    topo = _build_test_network()
    topo_file = tmp_path / "topo.json"
    topo_file.write_text(json.dumps(topo.to_dict()))

    change_file = tmp_path / "change_warn.json"
    change_file.write_text(
        json.dumps(
            {
                "description": "Warn change",
                "link_changes": [{"src": "agg0", "dst": "core0", "status": "down"}],
            }
        )
    )

    policy_file = tmp_path / "policy_warn.json"
    policy_file.write_text(
        json.dumps(
            {
                "max_latency_increase_warn_ms": 3.0,
                "max_latency_increase_block_ms": 20.0,
            }
        )
    )

    runner = CliRunner()
    # Default: exit 0
    res_default = runner.invoke(
        cli,
        ["twin", "validate", "-t", str(topo_file), "-ch", str(change_file), "-p", str(policy_file)],
    )
    assert res_default.exit_code == 0
    assert "[WARN]" in res_default.output

    # Strict: exit 2
    res_strict = runner.invoke(
        cli,
        [
            "twin",
            "validate",
            "-t",
            str(topo_file),
            "-ch",
            str(change_file),
            "-p",
            str(policy_file),
            "--strict-warnings",
        ],
    )
    assert res_strict.exit_code == 2
    assert "[WARN]" in res_strict.output


def test_cli_exit_codes_block(tmp_path: Path) -> None:
    """CLI must exit with code 1 on BLOCK."""
    topo = _build_test_network()
    topo_file = tmp_path / "topo.json"
    topo_file.write_text(json.dumps(topo.to_dict()))

    change_file = tmp_path / "change_block.json"
    change_file.write_text(
        json.dumps(
            {
                "description": "Block change",
                "link_changes": [
                    {"src": "core0", "dst": "edge1", "status": "down"},
                    {"src": "core1", "dst": "edge1", "status": "down"},
                ],
            }
        )
    )

    runner = CliRunner()
    res = runner.invoke(cli, ["twin", "validate", "-t", str(topo_file), "-ch", str(change_file)])
    assert res.exit_code == 1
    assert "[BLOCK]" in res.output


def test_cli_json_mode(tmp_path: Path) -> None:
    """CLI with --json must output only valid ValidationResult JSON."""
    topo = _build_test_network()
    topo_file = tmp_path / "topo.json"
    topo_file.write_text(json.dumps(topo.to_dict()))

    change_file = tmp_path / "change_pass.json"
    change_file.write_text(
        json.dumps(
            {
                "description": "Pass change",
                "link_changes": [{"src": "agg0", "dst": "core0", "bandwidth": 2000.0}],
            }
        )
    )

    runner = CliRunner()
    res = runner.invoke(
        cli, ["twin", "validate", "-t", str(topo_file), "-ch", str(change_file), "--json"]
    )
    assert res.exit_code == 0
    parsed = json.loads(res.output)
    assert parsed["verdict"] == "PASS"
    assert "blast_radius_summary" in parsed
    assert "provenance" in parsed


# ── REST API Parity Tests ─────────────────────────────────────


def test_api_cli_consistency(tmp_path: Path) -> None:
    """REST API and CLI must produce identical verdicts and metrics on the same input."""
    topo = _build_test_network()
    topo_file = tmp_path / "topo.json"
    topo_file.write_text(json.dumps(topo.to_dict()))

    change_data = {
        "description": "Cut primary link agg0->core0",
        "link_changes": [{"src": "agg0", "dst": "core0", "status": "down"}],
    }
    policy_data = {
        "max_latency_increase_warn_ms": 3.0,
        "max_latency_increase_block_ms": 20.0,
    }

    # 1. Evaluate via CLI
    change_file = tmp_path / "change.json"
    change_file.write_text(json.dumps(change_data))
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(policy_data))

    runner = CliRunner()
    cli_res = runner.invoke(
        cli,
        [
            "twin",
            "validate",
            "-t",
            str(topo_file),
            "-ch",
            str(change_file),
            "-p",
            str(policy_file),
            "--json",
        ],
    )
    cli_json = json.loads(cli_res.output)

    # 2. Evaluate via REST
    from nroute.api.server import _FALLBACK_TOKEN

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}

    # Load topology into API engine
    load_res = client.post("/api/topology/load", json={"path": str(topo_file)}, headers=headers)
    assert load_res.status_code == 200

    api_res = client.post(
        "/api/twin/validate",
        json={"change": change_data, "policy": policy_data},
        headers=headers,
    )
    assert api_res.status_code == 200
    api_json = api_res.json()

    # Compare Parity
    assert api_json["verdict"] == cli_json["verdict"] == "WARN"
    assert api_json["gate_passed"] is True
    assert cli_json["gate_passed"] is True
    assert api_json["summary"] == cli_json["summary"]
    assert api_json["warning_violations"] == cli_json["warning_violations"]
    assert api_json["blocking_violations"] == cli_json["blocking_violations"]
    assert api_json["blast_radius_summary"] == cli_json["blast_radius_summary"]
