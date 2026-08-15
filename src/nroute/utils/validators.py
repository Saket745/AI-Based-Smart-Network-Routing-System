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
   
    Validate that a value is a non-negative float.

    Args:
        value: The value to validate.
        name: The name of the parameter (for error messages).

    Returns:
        The validated value as a float.

    Raises:
       ValidationError: If the value is negative or not a number.
    
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
    
    Validate that a value is a valid probability (between 0.0 and 1.0 inclusive).

    Args:
        value: The value to validate.

    Returns:
        The validated probability as a float.

    Raises:
        ValidationError: If the value is not a valid probability.
    
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
    path: Any,
    must_exist: bool = False,
    allowed_roots: list[str | Path] | None = None,
) -> Path:
    
    Validate that a path is valid and optionally within allowed root directories to prevent path traversal.
=======
def validate_file_path(path: Any, must_exist: bool = True) -> Path:
    """
    Validate a file path to prevent security vulnerabilities and ensure existence.

    Args:
        path: The file path to validate.
        must_exist: Whether the path must exist on the file system.

    Returns:
        The validated, resolved Path object.

    Raises:
        ValidationError: If the path is invalid, empty, contains null bytes, or does not exist.
    """
    if not isinstance(path, (str, Path)):
        raise ValidationError("Invalid path format.")

    if isinstance(path, str):
        if not path.strip():
            raise ValidationError("File path cannot be empty.")
        if "\0" in path:
            raise ValidationError("Invalid path format.")
=======
    
=======
def validate_file_path(path: Any, must_exist: bool = False) -> Path:
    
    Validate that a path is valid and secure against path traversal vulnerabilities.
=======
def validate_file_path(path: Any, must_exist: bool = True) -> Path:

def validate_file_path(path: Any, must_exist: bool = False) -> Path:
    
    Validate that a path is correct and secure.

    Args:
        path: The path to validate, as a string or Path object.
        must_exist: If True, check if the file or directory exists.

    Returns:
        The validated and resolved Path object.

    Raises:
        ValidationError: If the path is empty, has invalid format, or does not exist.
    
    if not isinstance(path, (str, Path)):
        raise ValidationError("Invalid path format: path must be a string or Path object.")

=======
    
    if not isinstance(path, (str, Path)):
        raise ValidationError("Invalid path format: path must be a string or Path object.")
    # Check for empty path
    path_str = str(path).strip()
    if not path_str:
        raise ValidationError("Path cannot be empty.")

=======
    if "\0" in path_str:
        raise ValidationError("Invalid path format: path contains null bytes.")
    # Check for null bytes (security check for path traversal/injection)
    if "\0" in path_str:
        raise ValidationError("Invalid path format: path contains null bytes.")

    try:
        p = Path(path).resolve()
    except Exception as e:
        raise ValidationError(f"Invalid path format: {e}") from e

    if must_exist and not p.exists():
        raise ValidationError(f"Path '{p}' does not exist.")

    return p
=======
=======
    return p

def validate_file_path(path: Any, must_exist: bool = False) -> Path:
    
    Validate that a path is valid.

    Args:
        path: The path (str or Path) to validate.
        must_exist: Whether the path must exist.
        allowed_roots: Optional list of directories the path must reside under.
=======

    Returns:
        The validated path as a Path object.

    Raises:
        ValidationError: If the path is empty, invalid format, does not exist, or violates traversal restrictions.
    
    if isinstance(path, str) and path == "":
        raise ValidationError("Path cannot be empty.")

    if not isinstance(path, (str, Path)):
        raise ValidationError("Invalid path format.")

    try:
=======
        ValidationError: If the path is empty, invalid format, or does not exist.
    
    if not isinstance(path, (str, Path)):
        raise ValidationError("Invalid path format.")

    path_str = str(path).strip()
    if not path_str:
        raise ValidationError("Path cannot be empty.")

    if "\0" in path_str:
        raise ValidationError("Invalid path format.")

    try:
        p = Path(path)
        if must_exist:
            if not p.exists():
                raise ValidationError(f"File path '{path}' does not exist.")
            p = p.resolve()
        else:
            p.resolve()
    except (TypeError, ValueError, OSError) as e:
        raise ValidationError("Invalid path format.") from e

    return p
=======
                raise ValidationError(f"Path does not exist: {path}")
            p = p.resolve()
        else:
            p = p.resolve()
    except (TypeError, ValueError, OSError) as e:
        raise ValidationError(f"Invalid path format: {e}") from e

    return p

    try:
        p = Path(path).resolve()
    except (TypeError, ValueError, OSError) as e:
        raise ValidationError(f"Invalid path format: {e}") from e

    if must_exist and not p.exists():
        # Check for null bytes which cause ValueError/TypeError in Path/resolve on some systems
        if isinstance(path, str) and "\0" in path:
            raise ValidationError("Invalid path format.")
        p = Path(path)
        resolved = p.resolve()
    except (TypeError, ValueError, OSError) as e:
        raise ValidationError(f"Invalid path format: {e}") from e

    if must_exist and not resolved.exists():
        raise ValidationError(f"Path does not exist: {path}")

    if allowed_roots is not None:
        resolved_roots = []
        for r in allowed_roots:
            try:
                resolved_roots.append(Path(r).resolve())
            except Exception:
                continue
        if not any(resolved.is_relative_to(root) for root in resolved_roots):
            raise ValidationError("Access denied: Path is outside allowed directories.")

    return resolved
