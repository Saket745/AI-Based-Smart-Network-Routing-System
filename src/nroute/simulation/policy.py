"""Declarative Safety Policy & Validation Result Schemas for Pre-Flight Validation.

Defines:
  * ``ValidationVerdict``: Enum of possible gate decisions (PASS, WARN, BLOCK).
  * ``PolicyGateConfig``: Declarative threshold and rule configuration.
  * ``ValidationResult``: Machine-readable contract for CI/CD and API consumers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ValidationVerdict(str, Enum):
    """Possible outcomes of a pre-flight change validation."""

    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


class PolicyGateConfig(BaseModel):
    """Declarative safety policy defining thresholds for automated gating.

    Rules evaluate deterministically with strict hierarchical precedence:
    BLOCK > WARN > PASS.
    """

    schema_version: str = Field(default="1.0", description="Policy schema version")
    description: str = Field(
        default="Default Pre-Flight Safety Policy", description="Human-readable policy description"
    )

    # Latency thresholds (in milliseconds)
    max_latency_increase_warn_ms: float = Field(
        default=5.0,
        ge=0.0,
        description="Maximum allowed single-pair latency increase before triggering a WARN (ms)",
    )
    max_latency_increase_block_ms: float = Field(
        default=20.0,
        ge=0.0,
        description="Maximum allowed single-pair latency increase before triggering a BLOCK (ms)",
    )

    # Utilization thresholds (in [0.0, 1.0])
    max_utilization_warn: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Maximum allowed post-change link utilization before triggering a WARN",
    )
    max_utilization_block: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Maximum allowed post-change link utilization before triggering a BLOCK",
    )

    # Path-changed ratio thresholds (fraction of active pairs whose paths shifted)
    max_path_changed_ratio_warn: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Maximum fraction of node pairs with changed paths before triggering a WARN",
    )
    max_path_changed_ratio_block: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Maximum fraction of node pairs with changed paths before triggering a BLOCK",
    )

    # Reachability & Topology Protection
    allow_newly_unreachable: bool = Field(
        default=False,
        description="If False, any newly unreachable node pairs immediately trigger a BLOCK",
    )
    protected_nodes: list[str] = Field(
        default_factory=list,
        description="List of critical node IDs (e.g. core routers) that must remain 100% connected",
    )

    @model_validator(mode="after")
    def validate_threshold_consistency(self) -> PolicyGateConfig:
        """Enforce strict consistency between warning and blocking thresholds."""
        if self.max_latency_increase_warn_ms > self.max_latency_increase_block_ms:
            raise ValueError(
                f"max_latency_increase_warn_ms ({self.max_latency_increase_warn_ms}ms) "
                f"cannot exceed max_latency_increase_block_ms ({self.max_latency_increase_block_ms}ms)"
            )
        if self.max_utilization_warn > self.max_utilization_block:
            raise ValueError(
                f"max_utilization_warn ({self.max_utilization_warn}) "
                f"cannot exceed max_utilization_block ({self.max_utilization_block})"
            )
        if self.max_path_changed_ratio_warn > self.max_path_changed_ratio_block:
            raise ValueError(
                f"max_path_changed_ratio_warn ({self.max_path_changed_ratio_warn}) "
                f"cannot exceed max_path_changed_ratio_block ({self.max_path_changed_ratio_block})"
            )
        return self


class ValidationResult(BaseModel):
    """Standardized machine-readable result contract for pre-flight validation.

    Provides complete provenance, blast-radius metrics, and declarative gate evaluation.
    """

    schema_version: str = Field(default="1.0", description="Contract schema version")
    change_id: str = Field(default="", description="Identifier of the validated change")
    evaluation_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of evaluation")
    execution_duration_ms: float = Field(
        ..., ge=0.0, description="End-to-end evaluation latency in milliseconds"
    )

    # Policy Decision
    verdict: ValidationVerdict = Field(
        ..., description="Overall gate decision: PASS, WARN, or BLOCK"
    )
    gate_passed: bool = Field(
        ..., description="True if verdict is PASS (or WARN under permissive mode)"
    )
    summary: str = Field(..., description="Human-readable decision summary")
    blocking_violations: list[str] = Field(
        default_factory=list, description="List of all triggered BLOCK violations"
    )
    warning_violations: list[str] = Field(
        default_factory=list, description="List of all triggered WARN violations"
    )

    # Blast-Radius Summary
    blast_radius_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Key analytical blast-radius metrics (pairs analysed, unreachable, changed, latencies)",
    )
    critical_path_deltas: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top critical or newly unreachable path deltas",
    )

    # Provenance
    provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="Audit metadata (baseline topology hash, change patch hash, git SHA, routing engine)",
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a clean dictionary."""
        return self.model_dump()
