"""Unit tests for ModelStore model checkpointing, error handling, and integrity validation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nroute.exceptions import ModelError
from nroute.ml.model_store import ModelStore


class DummyModel:
    """A dummy model for testing ModelStore saving/loading."""

    def __init__(self, model_type: str = "custom", preferred_extension: str | None = None) -> None:
        self.model_type = model_type
        if preferred_extension is not None:
            self.preferred_extension = preferred_extension
        self.save_called = False
        self.load_called = False
        self.saved_path: str | None = None
        self.loaded_path: str | None = None

    def save(self, path: str) -> None:
        self.save_called = True
        self.saved_path = path
        with open(path, "w", encoding="utf-8") as f:
            f.write("dummy_weights_content")

    def load(self, path: str, allow_unsafe: bool = False) -> None:
        self.load_called = True
        self.loaded_path = path


def test_model_store_save_and_load_default() -> None:
    """Test saving and loading a model with default preferred_extension."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ModelStore(base_dir=tmpdir)
        model = DummyModel(model_type="xgboost")

        saved_path = store.save_model(model, name="test_model", version="1.0.0")
        assert Path(saved_path).exists()
        assert saved_path.endswith(".joblib")
        assert model.save_called
        assert model.saved_path == saved_path

        meta_path = Path(tmpdir) / "test_model_1.0.0.metadata.json"
        assert meta_path.exists()

        with open(meta_path, encoding="utf-8") as f:
            metadata = json.load(f)
        assert metadata["name"] == "test_model"
        assert metadata["version"] == "1.0.0"
        assert metadata["model_type"] == "xgboost"
        assert "sha256" in metadata

        loaded_model = DummyModel(model_type="xgboost")
        loaded_path = store.load_model(loaded_model, name="test_model", version="1.0.0")
        assert loaded_path == saved_path
        assert loaded_model.load_called
        assert loaded_model.loaded_path == loaded_path


def test_model_store_save_custom_extension() -> None:
    """Test saving a model with a custom preferred_extension property."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ModelStore(base_dir=tmpdir)
        model = DummyModel(model_type="my_nn", preferred_extension=".pt")

        saved_path = store.save_model(model, name="nn_model", version="2.1.0")
        assert saved_path.endswith(".pt")
        assert Path(saved_path).exists()

        loaded_model = DummyModel(model_type="my_nn")
        loaded_path = store.load_model(loaded_model, name="nn_model", version="2.1.0")
        assert loaded_path == saved_path


def test_model_store_integrity_check_failure() -> None:
    """Test that load_model fails if the checkpoint file is tampered with (checksum mismatch)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ModelStore(base_dir=tmpdir)
        model = DummyModel()

        saved_path = store.save_model(model, name="tamper_test", version="1.0.0")

        with open(saved_path, "w", encoding="utf-8") as f:
            f.write("tampered_content")

        loaded_model = DummyModel()
        with pytest.raises(ModelError, match="integrity validation failed"):
            store.load_model(loaded_model, name="tamper_test", version="1.0.0")


def test_model_store_missing_model_or_metadata() -> None:
    """Test loading nonexistent model name or version raises ModelError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ModelStore(base_dir=tmpdir)
        model = DummyModel()

        with pytest.raises(ModelError, match="No models found"):
            store.load_model(model, name="nonexistent")

        store.save_model(model, name="partial", version="1.0.0")

        with pytest.raises(ModelError, match=r"version '2\.0\.0' for 'partial' not found"):
            store.load_model(model, name="partial", version="2.0.0")


def test_load_model_no_valid_metadata_files() -> None:
    """Test that load_model raises ModelError when metadata files exist but are invalid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        store = ModelStore(base_dir=base_dir)

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

        meta_file = base_dir / "test_v1.metadata.json"
        meta_file.write_text("{}", encoding="utf-8")

        model = DummyModel()

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


def test_model_store_path_traversal_prevention() -> None:
    """Test that load_model rejects path traversal attempts in metadata file_path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "models"
        base_dir.mkdir()
        store = ModelStore(base_dir=base_dir)

        # Create an existing file outside base_dir
        outside_file = Path(tmpdir) / "secret.txt"
        outside_file.write_text("secret_data", encoding="utf-8")

        # Create metadata pointing outside base_dir to existing outside_file
        meta_file = base_dir / "traversal_v1.metadata.json"
        metadata = {
            "name": "traversal",
            "version": "1.0.0",
            "file_path": str(outside_file),
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "timestamp": "2026-01-01T00:00:00Z",
            "model_type": "custom",
        }
        meta_file.write_text(json.dumps(metadata), encoding="utf-8")

        model = DummyModel()
        with pytest.raises(ModelError, match="outside the allowed root"):
            store.load_model(model, "traversal", version="1.0.0")


def test_model_store_list_models() -> None:
    """Test listing models in the store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ModelStore(base_dir=tmpdir)
        model1 = DummyModel()
        model2 = DummyModel()

        store.save_model(model1, name="model_a", version="1.0.0")
        store.save_model(model2, name="model_b", version="2.0.0")

        models = store.list_models()
        assert len(models) == 2
        names = {m["name"] for m in models}
        assert names == {"model_a", "model_b"}
