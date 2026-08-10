"""Validation helpers for the nroute library."""

from __future__ import annotations

import math
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
