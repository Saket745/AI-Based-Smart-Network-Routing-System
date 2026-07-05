"""Unit tests for the dynamic class loader utility."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nroute.utils.loader import load_custom_class


def test_load_custom_class_invalid_format() -> None:
    """Test that invalid import formats raise ValueError."""
    with pytest.raises(ValueError, match="Invalid import target"):
        load_custom_class("no_colon")

    with pytest.raises(ValueError, match="Both module path and class name must be specified"):
        load_custom_class(":ClassName")

    with pytest.raises(ValueError, match="Both module path and class name must be specified"):
        load_custom_class("module:")

    with pytest.raises(ValueError, match="Both module path and class name must be specified"):
        load_custom_class("  :  ")


def test_load_custom_class_standard_module() -> None:
    """Test loading a class from a standard Python module."""
    # Using pathlib.Path as a stable example
    cls = load_custom_class("pathlib:Path")
    assert cls is Path


def test_load_custom_class_standard_module_not_found() -> None:
    """Test that non-existent modules raise ImportError."""
    with pytest.raises(ImportError, match="Failed to import module 'non_existent_module'"):
        load_custom_class("non_existent_module:MyClass")


def test_load_custom_class_class_not_found() -> None:
    """Test that missing classes in a module raise ImportError."""
    with pytest.raises(ImportError, match="Class 'NonExistent' not found in module 'pathlib'"):
        load_custom_class("pathlib:NonExistent")


def test_load_custom_class_not_a_class() -> None:
    """Test that targeting something that isn't a class raises ImportError."""
    # os.name is a string, not a class
    with pytest.raises(ImportError, match="is not a class type"):
        load_custom_class("os:name")


def test_load_custom_class_superclass_validation() -> None:
    """Test that superclass validation works correctly."""
    # Using a class from a standard library to avoid potential import issues with tests package
    from pathlib import Path, PurePath
    cls = load_custom_class("pathlib:Path", expected_superclass=PurePath)
    assert cls is Path

    with pytest.raises(TypeError, match="does not inherit from 'list'"):
        load_custom_class("pathlib:Path", expected_superclass=list)


def test_load_custom_class_local_file_disallowed() -> None:
    """Test that loading from local files is disallowed by default."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"class LocalClass:\n    pass\n")
        temp_path = f.name

    try:
        with pytest.raises(ImportError, match="Loading custom classes from local files is disallowed"):
            load_custom_class(f"{temp_path}:LocalClass", allow_unsafe=False)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_load_custom_class_local_file_success() -> None:
    """Test successful loading from a local Python file with allow_unsafe=True."""
    content = """
class LocalClass:
    def __init__(self):
        self.val = 42
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        cls = load_custom_class(f"{temp_path}:LocalClass", allow_unsafe=True)
        assert cls.__name__ == "LocalClass"
        obj = cls()
        assert obj.val == 42
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_load_custom_class_local_file_not_found() -> None:
    """Test that non-existent local files raise ImportError."""
    with pytest.raises(ImportError, match="Python file not found"):
        load_custom_class("non_existent_file_12345.py:MyClass", allow_unsafe=True)


def test_load_custom_class_local_file_execution_error() -> None:
    """Test that errors during local file execution are handled."""
    content = "raise RuntimeError('Boom')"
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        with pytest.raises(ImportError, match="Failed to execute module from file"):
            load_custom_class(f"{temp_path}:SomeClass", allow_unsafe=True)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_load_custom_class_local_file_spec_none() -> None:
    """Test that failure to get spec for a local file raises ImportError."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        temp_path = f.name

    try:
        with patch("importlib.util.spec_from_file_location", return_value=None):
            with pytest.raises(ImportError, match="Could not load spec for Python file"):
                load_custom_class(f"{temp_path}:SomeClass", allow_unsafe=True)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_load_custom_class_windows_drive_letter() -> None:
    """Test (mock) handling of Windows drive letters in paths."""
    # We can't easily test real Windows paths on Linux, but we can test the logic
    # if we can mock os.path.exists to return True for a path starting with C:

    # Actually the code does:
    # has_drive = len(import_str) > 1 and import_str[1] == ":" and import_str[0].isalpha()
    # search_str = import_str[2:] if has_drive else import_str

    # If I pass "C:/path/to/file.py:MyClass", it should not raise ValueError because of C:
    # but it will fail later because it doesn't exist.

    with pytest.raises(ImportError):
        load_custom_class("C:/non_existent.py:MyClass", allow_unsafe=True)

    # If I don't use allow_unsafe=True, it should fail with "disallowed" instead of "ValueError"
    # if it correctly identifies it as a path.
    # To be identified as a path, it needs to end with .py or exist.

    with pytest.raises(ImportError, match="Loading custom classes from local files is disallowed"):
        load_custom_class("C:/some/file.py:MyClass", allow_unsafe=False)
