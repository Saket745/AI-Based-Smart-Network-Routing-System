"""Utility functions for dynamically loading custom classes and modules."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


def _parse_import_target(import_str: str) -> tuple[str, str]:
    """Parse import target string into module/path part and class name."""
    import_str = import_str.strip()

    # Strip Windows drive letter (e.g. C:) from search_str to validate colon presence correctly
    has_drive = len(import_str) > 1 and import_str[1] == ":" and import_str[0].isalpha()
    search_str = import_str[2:] if has_drive else import_str

    if ":" not in search_str:
        raise ValueError(
            f"Invalid import target '{import_str}'. Expected format: 'path/to/file.py:ClassName' "
            "or 'package.module:ClassName'."
        )

    module_part, class_name = import_str.rsplit(":", 1)
    module_part = module_part.strip()
    class_name = class_name.strip()

    if not module_part or not class_name:
        raise ValueError(
            f"Invalid import target '{import_str}'. Both module path and class name must be specified."
        )

    return module_part, class_name


def _load_module_from_file(module_part: str, allow_unsafe: bool) -> Any:
    """Load a Python module dynamically from a file path."""
    if not allow_unsafe:
        raise PermissionError(
            f"Loading from a local Python file ('{module_part}') is restricted for "
            "security reasons. Use a standard module path or set allow_unsafe=True "
            "if you trust the source."
        )

    file_path = Path(module_part).resolve()
    if not file_path.is_file():
        raise ImportError(f"Python file not found: {file_path}")

    # Construct a unique module name based on file path
    module_name = f"nroute.dynamic.{file_path.stem}_{hash(str(file_path)) & 0xFFFFFFFF}"

    if module_name in sys.modules:
        return sys.modules[module_name]

    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for Python file: {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        raise ImportError(f"Failed to execute module from file '{file_path}': {e}") from e


def _extract_and_validate_class(
    module: Any, module_part: str, class_name: str, expected_superclass: type | None
) -> type:
    """Retrieve class attribute from module and validate type / inheritance."""
    if not hasattr(module, class_name):
        raise ImportError(f"Class '{class_name}' not found in module '{module_part}'.")

    cls = getattr(module, class_name)
    if not isinstance(cls, type):
        raise ImportError(f"Target '{class_name}' in module '{module_part}' is not a class type.")

    if expected_superclass is not None and not issubclass(cls, expected_superclass):
        raise TypeError(
            f"Target class '{class_name}' in module '{module_part}' does not inherit from '{expected_superclass.__name__}'."
        )

    return cls


def load_custom_class(
    import_str: str, expected_superclass: type | None = None, allow_unsafe: bool = False
) -> type:
    """
    Dynamically load a class from a module or a Python file.

    Supported formats:
        1. Local python file: "path/to/my_module.py:MyClass" (requires allow_unsafe=True)
        2. Standard Python module path: "my_package.module:MyClass"

    Args:
        import_str: The import target string in module:class or path:class format.
        expected_superclass: Optional superclass to validate inheritance against.
        allow_unsafe: Whether to allow loading from local filesystem paths.

    Returns:
        The loaded class type.

    Raises:
        ValueError: If the format is invalid.
        ImportError: If the module or class cannot be loaded.
        TypeError: If the class does not inherit from expected_superclass.
        PermissionError: If loading from a file is attempted with allow_unsafe=False.
    """
    module_part, class_name = _parse_import_target(import_str)

    # Check if module_part is a path to a local .py file
    if module_part.endswith(".py") or os.path.exists(module_part):
        module = _load_module_from_file(module_part, allow_unsafe=allow_unsafe)
    else:
        # Load as a standard Python module path
        try:
            module = importlib.import_module(module_part)
        except Exception as e:
            raise ImportError(f"Failed to import module '{module_part}': {e}") from e

    return _extract_and_validate_class(
        module, module_part, class_name, expected_superclass=expected_superclass
    )
