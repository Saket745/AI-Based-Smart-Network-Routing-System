"""nroute custom exception hierarchy."""

from __future__ import annotations

from typing import Any


class NRouteError(Exception):
    """Base exception class for all nroute errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TopologyError(NRouteError):
    """Raised when there is an issue with topology generation, mutation, or validation."""


class IngestionError(NRouteError):
    """Raised when parsing, loading, or validating ingested traffic/topology data fails."""


class RoutingError(NRouteError):
    """Raised when a route computation fails, or when a computed route is invalid."""


class SimulationError(NRouteError):
    """Raised during simulation execution, tick updates, or metrics collection."""


class ModelError(NRouteError):
    """Raised when ML model training, evaluation, loading, or prediction fails."""


class ConfigError(NRouteError):
    """Raised when a configuration value is invalid, missing, or malformed."""


class ValidationError(NRouteError):
    """Raised when domain validation rules are violated."""
