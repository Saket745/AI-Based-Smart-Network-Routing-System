"""Unit tests for the dynamic loader utility."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from nroute.utils.loader import load_custom_class


def test_load_standard_module_class() -> None:
    """Test loading a class from a standard Python module."""
    # Use pathlib.Path as a test target
    cls = load_custom_class("pathlib:Path")
    assert cls is Path
    assert isinstance(cls(), Path)


def test_load_standard_module_class_with_whitespace() -> None:
    """Test loading a class with extra whitespace in the import string."""
    cls = load_custom_class("  pathlib  :  Path  ")
    assert cls is Path


def test_load_from_local_file() -> None:
    """Test loading a class from a local Python file."""
    content = """
class MyDynamicClass:
    def greet(self):
        return "hello"

class AnotherClass:
    pass
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        cls = load_custom_class(f"{tmp_path}:MyDynamicClass")
        assert cls.__name__ == "MyDynamicClass"
        assert cls().greet() == "hello"

        # Verify we can load another class from the same file
        cls2 = load_custom_class(f"{tmp_path}:AnotherClass")
        assert cls2.__name__ == "AnotherClass"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_load_with_superclass_validation() -> None:
    """Test that superclass validation works correctly."""
    # Path inherits from object (obviously)
    cls = load_custom_class("pathlib:Path", expected_superclass=object)
    assert cls is Path

    # Test with a more specific superclass
    content = """
class Base:
    pass

class Derived(Base):
    pass
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Load the base class first so we can use it for validation
        base_cls = load_custom_class(f"{tmp_path}:Base")

        # Success case
        cls = load_custom_class(f"{tmp_path}:Derived", expected_superclass=base_cls)
        assert issubclass(cls, base_cls)

        # Failure case
        with pytest.raises(TypeError, match="does not inherit from 'Base'"):
            load_custom_class("pathlib:Path", expected_superclass=base_cls)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_invalid_format() -> None:
    """Test that invalid import formats raise ValueError."""
    with pytest.raises(ValueError, match="Expected format"):
        load_custom_class("pathlib.Path")  # Missing colon

    with pytest.raises(ValueError, match="Both module path and class name must be specified"):
        load_custom_class("pathlib:")

    with pytest.raises(ValueError, match="Both module path and class name must be specified"):
        load_custom_class(":Path")


def test_file_not_found() -> None:
    """Test that a non-existent Python file raises ImportError."""
    with pytest.raises(ImportError, match="Python file not found"):
        load_custom_class("non_existent_file_xyz.py:MyClass")


def test_module_not_found() -> None:
    """Test that a non-existent module raises ImportError."""
    with pytest.raises(ImportError, match="Failed to import module"):
        load_custom_class("nroute.non_existent_module:MyClass")


def test_class_not_found() -> None:
    """Test that a non-existent class in a module raises ImportError."""
    with pytest.raises(ImportError, match="Class 'NonExistentClass' not found"):
        load_custom_class("pathlib:NonExistentClass")


def test_not_a_class_type() -> None:
    """Test that a non-class target raises ImportError."""
    # os.getcwd is a function, not a class
    with pytest.raises(ImportError, match="is not a class type"):
        load_custom_class("os:getcwd")


def test_windows_drive_letter_logic() -> None:
    """
    Test the Windows drive letter stripping logic.
    Even on Linux, we can test the string manipulation logic.
    """
    # This won't actually load because C:/test.py doesn't exist,
    # but it should fail with "Python file not found" for C:/test.py
    # rather than a ValueError for invalid format.
    with pytest.raises(ImportError, match="Python file not found"):
        load_custom_class("C:/test.py:MyClass")


def test_failed_module_execution() -> None:
    """Test handling of modules that fail during execution."""
    content = "raise RuntimeError('Module load failed')"
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with pytest.raises(ImportError, match="Failed to execute module"):
            load_custom_class(f"{tmp_path}:MyClass")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
