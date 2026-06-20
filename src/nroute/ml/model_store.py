"""Model store for managing model checkpoints, versions, and integrity checksums."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nroute.exceptions import ModelError
from nroute.utils.logging import get_logger

logger = get_logger(__name__)


class ModelStore:
    """
    Manages loading, saving, versioning, and integrity checks (SHA-256) of ML models.
    """

    def __init__(self, base_dir: str | Path = "./models") -> None:
        """Initialize the ModelStore with a base storage directory."""
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _compute_sha256(self, filepath: Path) -> str:
        """Compute the SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def save_model(self, model: Any, name: str, version: str) -> str:
        """
        Save a model and generate its metadata JSON file with checksum.

        Args:
            model: The predictor or detector model instance (has save() method).
            name: Human-readable identifier for the model (e.g. 'congestion', 'anomaly').
            version: Semantic version string (e.g. 'v1.0.0').

        Returns:
            String representing the path to the saved model file.
        """
        ext = getattr(model, "preferred_extension", ".joblib")

        filename = f"{name}_{version}{ext}"
        model_path = self.base_dir / filename
        metadata_path = self.base_dir / f"{name}_{version}.metadata.json"

        try:
            # 1. Save model weights
            model.save(str(model_path))

            # 2. Compute checksum of saved file
            checksum = self._compute_sha256(model_path)

            # 3. Write metadata file
            metadata = {
                "name": name,
                "version": version,
                "file_path": str(model_path),
                "sha256": checksum,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_type": getattr(model, "model_type", "unknown"),
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            logger.info(
                "Model saved successfully", name=name, version=version, path=str(model_path)
            )
            return str(model_path)

        except Exception as e:
            raise ModelError(f"Failed to save model {name} (version {version}): {e}") from e

    def load_model(self, model: Any, name: str, version: str | None = None, allow_unsafe: bool = False) -> str:
        """
        Load a model from the store and verify its checksum integrity.

        Args:
            model: The predictor or detector instance to populate (has load() method).
            name: The name of the model to load.
            version: The version to load. If None, loads the latest version by timestamp.

        Returns:
            The loaded model's file path as a string.
        """
        metadata_files = list(self.base_dir.glob(f"{name}_*.metadata.json"))
        if not metadata_files:
            raise ModelError(f"No models found with name '{name}' in {self.base_dir}.")

        # Parse all metadata files
        metadata_list = []
        for mf in metadata_files:
            try:
                with open(mf, encoding="utf-8") as f:
                    meta = json.load(f)
                    meta["_meta_file"] = mf
                    metadata_list.append(meta)
            except Exception as e:
                logger.warning("Failed to read model metadata", file=str(mf), error=str(e))

        if not metadata_list:
            raise ModelError(f"No valid metadata files found for model '{name}'.")

        # Select target metadata
        target_meta = None
        if version is not None:
            for meta in metadata_list:
                if meta.get("version") == version:
                    target_meta = meta
                    break
            if not target_meta:
                raise ModelError(f"Model version '{version}' for '{name}' not found.")
        else:
            # Sort by timestamp to find latest
            try:
                metadata_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                target_meta = metadata_list[0]
            except Exception as e:
                raise ModelError(f"Failed to parse timestamps to find latest model: {e}") from e

        model_path = Path(target_meta["file_path"])
        expected_sha = target_meta["sha256"]

        if not model_path.is_file():
            # Try loading relative to base directory in case path is absolute to different workspace
            alt_path = self.base_dir / model_path.name
            if alt_path.is_file():
                model_path = alt_path
            else:
                raise ModelError(f"Model file not found: {model_path}")

        # Check integrity
        actual_sha = self._compute_sha256(model_path)
        if actual_sha != expected_sha:
            raise ModelError(
                f"Model integrity validation failed for {model_path}.\n"
                f"  Expected SHA-256: {expected_sha}\n"
                f"  Actual SHA-256:   {actual_sha}"
            )

        try:
            import inspect
            sig = inspect.signature(model.load)
            if "allow_unsafe" in sig.parameters:
                model.load(str(model_path), allow_unsafe=allow_unsafe)
            else:
                model.load(str(model_path))
            logger.info(
                "Model loaded and verified",
                name=name,
                version=target_meta.get("version"),
                path=str(model_path),
            )
            return str(model_path)
        except Exception as e:
            raise ModelError(f"Failed to load model state from file {model_path}: {e}") from e

    def list_models(self) -> list[dict[str, Any]]:
        """List all saved models and their metadata details."""
        models = []
        for mf in self.base_dir.glob("*.metadata.json"):
            try:
                with open(mf, encoding="utf-8") as f:
                    meta = json.load(f)
                    models.append(meta)
            except Exception:
                pass
        return models
