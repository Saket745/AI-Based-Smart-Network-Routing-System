"""Unit tests for ModelStore error handling paths."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nroute.exceptions import ModelError
from nroute.ml.model_store import ModelStore


class DummyModel:
    """A dummy model for testing."""

    def load(self, path: str, allow_unsafe: bool = False) -> None:
        pass


def test_load_model_no_valid_metadata_files() -> None:
    """Test that load_model raises ModelError when metadata files exist but are invalid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = ModelStore(base_dir=base_dir)

        # Create a malformed metadata file that matches the glob
        meta_file = base_dir / "test_v1.metadata.json"
        meta_file.write_text("not a json content", encoding="utf-8")

        model = DummyModel()
        with pytest.raises(ModelError, match="No valid metadata files found for model 'test'"):
            store.load_model(model, "test")


def test_load_model_metadata_open_exception() -> None:
    """Test that load_model handles generic exceptions during metadata file opening."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = ModelStore(base_dir=base_dir)

        # Create a metadata file
        meta_file = base_dir / "test_v1.metadata.json"
        meta_file.write_text("{}", encoding="utf-8")

        model = DummyModel()

        # Mock open to raise an exception when reading the metadata file
        original_open = open

        def mocked_open(file: str | Path, *args, **kwargs):
            if str(file).endswith(".metadata.json"):
                raise OSError("Simulated permission error")
            return original_open(file, *args, **kwargs)

        with (
            patch("builtins.open", side_effect=mocked_open),
            pytest.raises(ModelError, match="No valid metadata files found for model 'test'"),
        ):
            store.load_model(model, "test")
