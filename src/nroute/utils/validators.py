"""Validation helpers for the nroute library."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from nroute.exceptions import ValidationError


def validate_node_id(node_id: Any) -> str:
    """
    Validate that a node ID is a non-empty string.

    Accepts strings, integers, and finite floats (coerced to string).
    Rejects booleans, NaN, and Infinity.
    """
    if isinstance(node_id, bool):
        raise ValidationError("Node ID cannot be a boolean.")

    if isinstance(node_id, int | float):
        if isinstance(node_id, float) and (math.isnan(node_id) or math.isinf(node_id)):
            raise ValidationError(f"Node ID cannot be {node_id}.")
        node_id = str(node_id)

    if not isinstance(node_id, str):
        raise ValidationError(f"Node ID must be a string, got {type(node_id).__name__}.")

    cleaned = node_id.strip()
    if not cleaned:
        raise ValidationError("Node ID cannot be an empty or whitespace-only string.")

    return cleaned


def validate_positive_float(value: Any, name: str) -> float:
    """Validate that a value is a non-negative float."""
    try:
        val = float(value)
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f"Parameter '{name}' must be a number, got type {type(value).__name__}."
        ) from e

    if val < 0.0 or math.isnan(val):
        raise ValidationError(f"Parameter '{name}' must be a non-negative number, got {val}.")

    return val


def validate_probability(value: Any) -> float:
    """Validate that a value is a valid probability between 0.0 and 1.0 inclusive."""
    try:
        val = float(value)
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f"Probability must be a number, got type {type(value).__name__}."
        ) from e

    if not (0.0 <= val <= 1.0):
        raise ValidationError(f"Probability must be between 0.0 and 1.0, got {val}.")

    return val


def validate_file_path(path: Any, must_exist: bool = False) -> Path:
    """
    Validate and resolve a filesystem path safely.

    Args:
        path: The path to validate, as a string or Path object.
        must_exist: If True, require the resolved path to exist.

    Returns:
        The validated and resolved Path object.

    Raises:
        ValidationError: If the path is invalid or does not exist when required.
    """
    if not isinstance(path, (str, Path)):
        raise ValidationError("Invalid path format: path must be a string or Path object.")

    path_str = str(path).strip()
    if not path_str:
        raise ValidationError("Path cannot be empty.")

    if "\0" in path_str:
        raise ValidationError("Invalid path format: path contains null bytes.")

    try:
        resolved = Path(path).resolve()
    except (TypeError, ValueError, OSError) as e:
        raise ValidationError(f"Invalid path format: {e}") from e

    if must_exist and not resolved.exists():
        raise ValidationError(f"Path '{resolved}' does not exist.")

    return resolved
