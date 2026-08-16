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
    """Validate that a value is a non-negative finite float."""
    try:
        val = float(value)
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f"Parameter '{name}' must be a number, got type {type(value).__name__}."
        ) from e

    if val < 0.0 or math.isnan(val):
        raise ValidationError(f"Parameter '{name}' must be a non-negative number, got {val}.")

    return val


def validate_file_path(
    path: Any, must_exist: bool = True, allowed_root: str | Path | None = None
) -> Path:
    """
    Validate a path and optionally constrain it to an allowed directory.

    The optional ``allowed_root`` containment check prevents path traversal
    when untrusted input is used to select files.
    """
    if not isinstance(path, (str, Path)):
        raise ValidationError("Invalid path format: path must be a string or Path object.")
    if isinstance(path, str) and not path.strip():
        raise ValidationError("File path cannot be empty.")
    if isinstance(path, str) and "\0" in path:
        raise ValidationError("Invalid path format: null bytes are not allowed in path.")

    try:
        validated_path = Path(path).resolve()
        if allowed_root is not None:
            root = Path(allowed_root).resolve()
            try:
                validated_path.relative_to(root)
            except ValueError as e:
                raise ValidationError(
                    f"Path '{validated_path}' is outside the allowed root '{root}'."
                ) from e
    except (TypeError, ValueError, OSError) as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(f"Invalid path format: {e}") from e

    if must_exist:
        try:
            if not validated_path.exists():
                raise ValidationError(f"File '{validated_path}' does not exist.")
        except (OSError, ValueError) as e:
            raise ValidationError(f"Invalid path format: {e}") from e

    return validated_path


def validate_probability(value: Any) -> float:
    """Validate that a value is a valid probability between 0.0 and 1.0."""
    try:
        val = float(value)
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f"Probability must be a number, got type {type(value).__name__}."
        ) from e

    if not (0.0 <= val <= 1.0):
        raise ValidationError(f"Probability must be between 0.0 and 1.0, got {val}.")

    return val
