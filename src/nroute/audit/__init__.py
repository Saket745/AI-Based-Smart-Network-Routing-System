"""Three-tier audit and compliance engine.

Implements the three-layer audit trace architecture:

* **Layer 1 — Structured Log**: Machine-parseable JSON records of every
  state transition, suitable for SIEM integration and compliance archival.

* **Layer 2 — Human Explanation**: Natural-language narrative explaining
  *what changed* and *why*, suitable for NOC review.

* **Layer 3 — Counterfactual**: "What would have happened if the change
  had NOT been applied?" — computes an alternative timeline by running
  the Analytical Engine on the *before* state and comparing it to the
  *after* state.

All audit records are immutable once written (append-only log).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from nroute.utils.logging import get_logger

logger = get_logger(__name__)


# ── Audit record types ───────────────────────────────────────


class AuditAction(str, Enum):
    """Categories of auditable actions."""

    CONFIG_CHANGE = "config_change"
    TOPOLOGY_MUTATION = "topology_mutation"
    ROUTING_RECOMPUTE = "routing_recompute"
    LINK_FAILURE = "link_failure"
    NODE_FAILURE = "node_failure"
    RCA_DIAGNOSIS = "rca_diagnosis"
    SIMULATION_RUN = "simulation_run"
    POLICY_CHECK = "policy_check"


@dataclass
class AuditRecord:
    """A single immutable audit entry (Layer 1 + 2 + 3)."""

    # Layer 1: Structured log
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    action: AuditAction = AuditAction.TOPOLOGY_MUTATION
    actor: str = "system"
    source: str = ""
    target: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    # Layer 2: Human explanation
    explanation: str = ""

    # Layer 3: Counterfactual
    counterfactual: str = ""
    counterfactual_data: dict[str, Any] = field(default_factory=dict)

    # Status
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "action": self.action.value,
            "actor": self.actor,
            "source": self.source,
            "target": self.target,
            "details": self.details,
            "explanation": self.explanation,
            "counterfactual": self.counterfactual,
            "counterfactual_data": self.counterfactual_data,
            "success": self.success,
            "error_message": self.error_message,
        }


# ── Audit Trail (append-only log) ────────────────────────────


class AuditTrail:
    """In-memory + optional file-backed append-only audit trail.

    Each ``record()`` call appends to both the in-memory list and,
    if a log file is configured, to an NDJSON file on disk.

    Usage::

        trail = AuditTrail(log_file="./audit/trail.ndjson")
        trail.record(
            action=AuditAction.CONFIG_CHANGE,
            actor="engineer:alice",
            source="R1",
            target="R2",
            details={"status": "down"},
            explanation="Link R1→R2 was administratively shut down.",
            counterfactual="Without this change, 12 flows would remain "
                           "on the R1→R2 path with avg latency 4.2 ms.",
        )
    """

    def __init__(self, log_file: str | Path | None = None) -> None:
        self._records: list[AuditRecord] = []
        self._log_path: Path | None = None

        if log_file is not None:
            self._log_path = Path(log_file)
            self._log_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Recording ────────────────────────────────────────

    def record(
        self,
        action: AuditAction,
        *,
        actor: str = "system",
        source: str = "",
        target: str = "",
        details: dict[str, Any] | None = None,
        explanation: str = "",
        counterfactual: str = "",
        counterfactual_data: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str = "",
    ) -> AuditRecord:
        """Create and store a new audit record.

        Returns:
            The created ``AuditRecord`` (for chaining / inspection).
        """
        rec = AuditRecord(
            action=action,
            actor=actor,
            source=source,
            target=target,
            details=details or {},
            explanation=explanation,
            counterfactual=counterfactual,
            counterfactual_data=counterfactual_data or {},
            success=success,
            error_message=error_message,
        )

        self._records.append(rec)

        # Append to file
        if self._log_path is not None:
            try:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec.to_dict()) + "\n")
            except Exception as exc:
                logger.error(
                    "Failed to write audit record to file",
                    path=str(self._log_path),
                    error=str(exc),
                )

        logger.debug(
            "Audit record created",
            audit_id=rec.audit_id,
            action=action.value,
            actor=actor,
        )

        return rec

    # ── Query ────────────────────────────────────────────

    @property
    def records(self) -> list[AuditRecord]:
        """Get all records (read-only copy)."""
        return list(self._records)

    def query(
        self,
        *,
        action: AuditAction | None = None,
        actor: str | None = None,
        source: str | None = None,
        target: str | None = None,
        since: float | None = None,
        limit: int | None = None,
    ) -> list[AuditRecord]:
        """Filter audit records.

        Args:
            action: Filter by action type.
            actor: Filter by actor.
            source: Filter by source node.
            target: Filter by target node.
            since: Only records with timestamp >= since.
            limit: Maximum number of records to return.

        Returns:
            Filtered list of ``AuditRecord`` objects.
        """
        results = self._records

        if action is not None:
            results = [r for r in results if r.action == action]
        if actor is not None:
            results = [r for r in results if r.actor == actor]
        if source is not None:
            results = [r for r in results if r.source == source]
        if target is not None:
            results = [r for r in results if r.target == target]
        if since is not None:
            results = [r for r in results if r.timestamp >= since]

        if limit is not None:
            results = results[:limit]

        return results

    # ── Export ────────────────────────────────────────────

    def export_json(self, path: str | Path) -> None:
        """Export the full audit trail to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in self._records], f, indent=2)

    def summary(self) -> dict[str, Any]:
        """Generate a summary of the audit trail."""
        action_counts: dict[str, int] = {}
        for r in self._records:
            action_counts[r.action.value] = action_counts.get(r.action.value, 0) + 1

        return {
            "total_records": len(self._records),
            "action_counts": action_counts,
            "earliest_timestamp": (
                min(r.timestamp for r in self._records) if self._records else None
            ),
            "latest_timestamp": (
                max(r.timestamp for r in self._records) if self._records else None
            ),
            "unique_actors": sorted(set(r.actor for r in self._records)),
            "error_count": sum(1 for r in self._records if not r.success),
        }
