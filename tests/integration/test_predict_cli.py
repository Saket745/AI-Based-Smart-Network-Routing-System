"""Integration tests for congestion prediction CLI edge cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from nroute.cli import cli


class _FakePredictor:
    """Minimal predictor stub so tests exercise CLI feedback only."""

    def load(self, path: str, allow_unsafe: bool = False) -> None:
        del path, allow_unsafe

    def predict(self, features: Any) -> Any:
        del features
        raise AssertionError("predict() must not run for an edgeless topology")


def _write_edgeless_topology(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "node-a", "type": "router"},
                    {"id": "node-b", "type": "router"},
                ],
                "edges": [],
            }
        )
    )


def test_predict_congestion_edgeless_text_feedback(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Edgeless text output explains the issue and offers actionable next steps."""
    from nroute.ml import congestion as congestion_module

    monkeypatch.setattr(congestion_module, "CongestionPredictor", _FakePredictor)

    topology_path = tmp_path / "edgeless.json"
    model_path = tmp_path / "model.bin"
    _write_edgeless_topology(topology_path)
    model_path.write_text("placeholder")

    result = CliRunner().invoke(
        cli,
        [
            "predict",
            "congestion",
            "--topology",
            str(topology_path),
            "--model",
            str(model_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "No links found in topology" in result.output
    assert "Add links between topology nodes" in result.output
    assert "Check the topology file if edges were expected" in result.output


def test_predict_congestion_edgeless_json_feedback(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Edgeless JSON output stays machine-readable and exposes next steps."""
    from nroute.ml import congestion as congestion_module

    monkeypatch.setattr(congestion_module, "CongestionPredictor", _FakePredictor)

    topology_path = tmp_path / "edgeless.json"
    model_path = tmp_path / "model.bin"
    _write_edgeless_topology(topology_path)
    model_path.write_text("placeholder")

    result = CliRunner().invoke(
        cli,
        [
            "--output-format",
            "json",
            "predict",
            "congestion",
            "--topology",
            str(topology_path),
            "--model",
            str(model_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["links"] == []
    assert data["congested_count"] == 0
    assert "No links found in topology" in data["warning"]
    assert len(data["next_steps"]) == 2
