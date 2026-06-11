"""Validation helpers for the nroute library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nroute.exceptions import ValidationError


def validate_node_id(node_id: Any) -> str:
    """
    Validate that a node ID is a non-empty string.

    Args:
        node_id: The node ID to validate.

    Returns:
        The validated node ID as a string.

    Raises:
        ValidationError: If the node ID is invalid.
    """
    if isinstance(node_id, (int, float)):
        node_id = str(node_id)

    if not isinstance(node_id, str):
        raise ValidationError(
            f"Node ID must be a string, got {type(node_id).__name__}."
        )

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

    if val < 0.0:
        raise ValidationError(f"Parameter '{name}' must be non-negative, got {val}.")

    return val


def validate_file_path(path: Any, must_exist: bool = True) -> Path:
    """
    Validate that a file path is valid and optionally exists.

    Args:
        path: The path to validate (str or Path).
        must_exist: If True, check if the file exists on the filesystem.

    Returns:
        The validated Path object.

    Raises:
        ValidationError: If the path is invalid or does not exist.
    """
    if not path:
        raise ValidationError("Path cannot be empty.")

    try:
        validated_path = Path(path).resolve()
    except Exception as e:
        raise ValidationError(f"Invalid path format: {path}.") from e

    if must_exist and not validated_path.exists():
        raise ValidationError(f"Path does not exist: {validated_path}.")

    return validated_path


def validate_probability(value: Any) -> float:
    """
    Validate that a value is a valid probability (between 0.0 and 1.0 inclusive).

    Args:
        value: The value to validate.

    Returns:
        The validated probability as a float.

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
