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

    Args:
        node_id: The node ID to validate.

    Returns:
        The validated node ID as a string.

    Raises:
        ValidationError: If the node ID is invalid.
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
    """
    Validate that a value is a non-negative float.

    Args:
        value: The value to validate.
        name: The name of the parameter (for error messages).

    Returns:
        The validated value as a float.

    Raises:
        ValidationError: If the value is negative or not a number.
    """
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
    """
    Validate that a value is a valid probability (between 0.0 and 1.0 inclusive).

    Args:
        value: The value to validate.

    Returns:
        The validated value as a float.

    Raises:
        ValidationError: If the value is not a valid probability.
    """
    try:
        val = float(value)
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f"Probability must be a number, got type {type(value).__name__}."
        ) from e

    if not (0.0 <= val <= 1.0):
        raise ValidationError(f"Probability must be between 0.0 and 1.0, got {val}.")

    return val


def validate_file_path(
    path: Any, must_exist: bool = True, allowed_root: str | Path | None = None
) -> Path:
    """
    Validate that a file path is valid and optionally exists within a trusted root.

    Args:
        path: The path to validate (str or Path).
        must_exist: Whether the file must exist.
        allowed_root: Optional trusted directory that the resolved path must stay within.

    Returns:
        The validated path as a Path object.

    Raises:
        ValidationError: If the path is invalid, missing, or outside allowed_root.
    """
    if not isinstance(path, (str, Path)):
        raise ValidationError("Invalid path format: path must be a string or Path object.")

    if isinstance(path, str) and not path.strip():
        raise ValidationError("File path cannot be empty.")

    if isinstance(path, str) and "\0" in path:
        raise ValidationError("Invalid path format: null bytes are not allowed in path.")

    try:
        p = Path(path)
        if allowed_root is not None:
            root = Path(allowed_root).resolve()
            p_resolved = p.resolve()
            try:
                p_resolved.relative_to(root)
            except ValueError as e:
                raise ValidationError(
                    f"Path '{p_resolved}' is outside the allowed root '{root}'."
                ) from e
        else:
            p_resolved = p
    except (TypeError, ValueError, OSError) as e:
        raise ValidationError(f"Invalid path format: {e}") from e

    if must_exist:
        try:
            if not p_resolved.exists():
                raise ValidationError(f"File '{p_resolved}' does not exist.")
        except (OSError, ValueError) as e:
            raise ValidationError(f"Invalid path format: {e}") from e
        return p_resolved.resolve()

    return p_resolved
