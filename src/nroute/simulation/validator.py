"""Pre-Flight Validation Service for Network Digital Twin.

Orchestrates:
  1. Input validation & cryptographic provenance hashing.
  2. Analytical change-impact simulation via ``ChangeImpactSimulator``.
  3. Declarative safety policy evaluation with strict precedence (BLOCK > WARN > PASS).
  4. Construction of the machine-readable ``ValidationResult`` contract.
"""

from __future__ import annotations

import datetime
import functools
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from nroute.core.openconfig import ConfigChange
from nroute.simulation.change_impact import ChangeImpactSimulator
from nroute.simulation.policy import (
    PolicyGateConfig,
    ValidationResult,
    ValidationVerdict,
)
from nroute.utils.logging import get_logger

if TYPE_CHECKING:
    from nroute.core.topology import Topology
    from nroute.simulation.change_impact import BlastRadius

logger = get_logger(__name__)


def _compute_sha256(data: str | bytes | dict[str, Any]) -> str:
    """Compute SHA-256 hash of text, bytes, or JSON-serializable dictionary."""
    if isinstance(data, dict):
        raw = json.dumps(data, default=str).encode("utf-8")
    elif isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = data
    return hashlib.sha256(raw).hexdigest()


@functools.lru_cache(maxsize=1)
def _get_git_sha() -> str:
    """Retrieve current Git commit SHA safely (cached)."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return "unknown_sha"


class PreFlightValidator:
    """Core validator executing deterministic pre-flight network change gating."""

    @staticmethod
    def validate(
        topology: Topology,
        change: ConfigChange | dict[str, Any] | str | Path,
        policy: PolicyGateConfig | dict[str, Any] | str | Path | None = None,
        weight: str = "latency",
    ) -> ValidationResult:
        """Run pre-flight validation on a proposed change against a safety policy.

        Args:
            topology: The baseline network topology.
            change: Proposed configuration change (ConfigChange, dict, or file path).
            policy: Declarative safety policy (PolicyGateConfig, dict, file path, or None).
            weight: Edge attribute used as routing weight metric (default: 'latency').

        Returns:
            A validated ``ValidationResult`` instance.
        """
        t0 = time.perf_counter()

        # 1. Parse and validate change patch
        change_raw: dict[str, Any] = {}
        change_id: str = "CHG-ANONYMOUS"

        if isinstance(change, (str, Path)):
            p = Path(change)
            if not p.is_file():
                raise FileNotFoundError(f"Change patch file not found: {change}")
            content = p.read_text(encoding="utf-8")
            change_raw = (
                yaml.safe_load(content)
                if p.suffix.lower() in (".yaml", ".yml")
                else json.loads(content)
            )
            change_id = change_raw.get("change_id", p.stem)
            config_change = ConfigChange.model_validate(change_raw)
            change_hash = _compute_sha256(content)
        elif isinstance(change, dict):
            change_raw = change
            change_id = change_raw.get("change_id", "CHG-INLINE")
            config_change = ConfigChange.model_validate(change_raw)
            change_hash = _compute_sha256(change_raw)
        elif isinstance(change, ConfigChange):
            config_change = change
            change_raw = config_change.model_dump()
            change_id = getattr(config_change, "change_id", "CHG-OBJECT")
            change_hash = _compute_sha256(change_raw)
        else:
            raise TypeError(f"Unsupported change input type: {type(change)}")

        # 2. Parse and validate policy configuration
        if policy is None:
            gate_policy = PolicyGateConfig()
            policy_hash = _compute_sha256(gate_policy.model_dump())
        elif isinstance(policy, (str, Path)):
            p = Path(policy)
            if not p.is_file():
                raise FileNotFoundError(f"Policy configuration file not found: {policy}")
            content = p.read_text(encoding="utf-8")
            policy_raw = (
                yaml.safe_load(content)
                if p.suffix.lower() in (".yaml", ".yml")
                else json.loads(content)
            )
            gate_policy = PolicyGateConfig.model_validate(policy_raw)
            policy_hash = _compute_sha256(content)
        elif isinstance(policy, dict):
            gate_policy = PolicyGateConfig.model_validate(policy)
            policy_hash = _compute_sha256(policy)
        elif isinstance(policy, PolicyGateConfig):
            gate_policy = policy
            policy_hash = _compute_sha256(gate_policy.model_dump())
        else:
            raise TypeError(f"Unsupported policy input type: {type(policy)}")

        # 3. Baseline topology provenance
        topo_dict = topology.to_dict()
        baseline_hash = _compute_sha256(topo_dict)

        # 4. Execute analytical change simulation
        simulator = ChangeImpactSimulator(topology)
        blast: BlastRadius = simulator.simulate(config_change, weight=weight)

        # 5. Evaluate declarative policy rules
        blocking_violations: list[str] = []
        warning_violations: list[str] = []

        total_pairs = blast.total_pairs_analysed
        path_changed_ratio = (blast.path_changed_pairs / total_pairs) if total_pairs > 0 else 0.0

        # Check Blocking Conditions
        if blast.newly_unreachable_pairs > 0 and not gate_policy.allow_newly_unreachable:
            blocking_violations.append(
                f"Newly unreachable pairs ({blast.newly_unreachable_pairs}) detected: network connectivity was severed."
            )

        if gate_policy.protected_nodes:
            for p_node in gate_policy.protected_nodes:
                # Check if protected node suffered reachability loss
                lost_pairs = [
                    d
                    for d in blast.path_deltas
                    if (d.source == p_node or d.destination == p_node) and d.became_unreachable
                ]
                if lost_pairs:
                    blocking_violations.append(
                        f"Protected node '{p_node}' lost reachability to {len(lost_pairs)} destination(s)."
                    )

        if blast.max_latency_increase >= gate_policy.max_latency_increase_block_ms:
            blocking_violations.append(
                f"Max latency increase (+{blast.max_latency_increase:.2f}ms) exceeds block threshold ({gate_policy.max_latency_increase_block_ms:.2f}ms)."
            )

        if path_changed_ratio >= gate_policy.max_path_changed_ratio_block:
            blocking_violations.append(
                f"Path change ratio ({path_changed_ratio * 100:.1f}%) exceeds block threshold ({gate_policy.max_path_changed_ratio_block * 100:.1f}%)."
            )

        # Check Warning Conditions (if not already blocked on the same dimension)
        if (
            blast.max_latency_increase >= gate_policy.max_latency_increase_warn_ms
            and blast.max_latency_increase < gate_policy.max_latency_increase_block_ms
        ):
            warning_violations.append(
                f"Max latency increase (+{blast.max_latency_increase:.2f}ms) exceeds warning threshold ({gate_policy.max_latency_increase_warn_ms:.2f}ms)."
            )

        if (
            path_changed_ratio >= gate_policy.max_path_changed_ratio_warn
            and path_changed_ratio < gate_policy.max_path_changed_ratio_block
        ):
            warning_violations.append(
                f"Path change ratio ({path_changed_ratio * 100:.1f}%) exceeds warning threshold ({gate_policy.max_path_changed_ratio_warn * 100:.1f}%)."
            )

        # 6. Assign Verdict based on strict precedence: BLOCK > WARN > PASS
        if blocking_violations:
            verdict = ValidationVerdict.BLOCK
            gate_passed = False
            summary = f"REJECTED: Proposed change violates {len(blocking_violations)} blocking safety rule(s)."
        elif warning_violations:
            verdict = ValidationVerdict.WARN
            gate_passed = True
            summary = f"WARNING: Proposed change triggered {len(warning_violations)} warning threshold(s)."
        else:
            verdict = ValidationVerdict.PASS
            gate_passed = True
            summary = "PASSED: Proposed change cleared all declarative safety gates."

        exec_duration_ms = (time.perf_counter() - t0) * 1000.0

        # 7. Construct Blast-Radius Summary & Critical Path Deltas
        blast_summary = {
            "total_pairs_analysed": blast.total_pairs_analysed,
            "unreachable_pairs_before": blast.unreachable_pairs_before,
            "unreachable_pairs_after": blast.unreachable_pairs_after,
            "newly_unreachable_pairs": blast.newly_unreachable_pairs,
            "newly_reachable_pairs": blast.newly_reachable_pairs,
            "path_changed_pairs": blast.path_changed_pairs,
            "path_changed_ratio": round(path_changed_ratio, 4),
            "affected_nodes_count": len(blast.affected_nodes),
            "affected_edges_count": len(blast.affected_edges),
            "avg_latency_before_ms": round(blast.avg_latency_before, 3),
            "avg_latency_after_ms": round(blast.avg_latency_after, 3),
            "max_latency_increase_ms": round(blast.max_latency_increase, 3),
        }

        critical_deltas = [
            {
                "source": d.source,
                "destination": d.destination,
                "before_path": d.before_path,
                "after_path": d.after_path,
                "before_latency": round(d.before_latency, 3),
                "after_latency": round(d.after_latency, 3),
                "latency_delta_ms": round(d.after_latency - d.before_latency, 3),
                "became_unreachable": d.became_unreachable,
                "path_changed": d.path_changed,
            }
            for d in blast.path_deltas
            if d.became_unreachable
            or (
                d.path_changed
                and (d.after_latency - d.before_latency) >= gate_policy.max_latency_increase_warn_ms
            )
        ]

        # 8. Assemble Provenance & Return ValidationResult
        provenance = {
            "baseline_topology_hash": baseline_hash,
            "change_patch_hash": change_hash,
            "policy_hash": policy_hash,
            "git_sha": _get_git_sha(),
            "routing_engine": f"AnalyticalEngine (weight={weight})",
        }

        return ValidationResult(
            schema_version="1.0",
            change_id=str(change_id),
            evaluation_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            execution_duration_ms=round(exec_duration_ms, 3),
            verdict=verdict,
            gate_passed=gate_passed,
            summary=summary,
            blocking_violations=blocking_violations,
            warning_violations=warning_violations,
            blast_radius_summary=blast_summary,
            critical_path_deltas=critical_deltas,
            provenance=provenance,
        )
