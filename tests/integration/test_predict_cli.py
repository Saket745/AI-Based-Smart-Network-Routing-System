"""Integration coverage for congestion prediction edge cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from nroute.cli import cli


class _FakePredictor:
    def load(self, path: str, allow_unsafe: bool = False) -> None:
        del path, allow_unsafe

    def predict(self, features: Any) -> Any:
        raise AssertionError(f"Unexpected prediction call: {features}")


def test_predict_congestion_edgeless_feedback(monkeypatch: Any, tmp_path: Path) -> None:
    """Edgeless text output is actionable and JSON output stays structured."""
    from nroute.ml import congestion as congestion_module

    monkeypatch.setattr(congestion_module, "CongestionPredictor", _FakePredictor)
    topology = tmp_path / "edgeless.json"
    topology.write_text(json.dumps({"nodes": [{"id": "a"}, {"id": "b"}], "edges": []}))
    model = tmp_path / "model.bin"
    model.write_text("placeholder")
    args = ["predict", "congestion", "--topology", str(topology), "--model", str(model)]

    text = CliRunner().invoke(cli, args, catch_exceptions=False)
    assert text.exit_code == 0
    assert "No links found in topology" in text.output
    assert "Add links between topology nodes" in text.output

    payload = CliRunner().invoke(
        cli, ["--output-format", "json", *args], catch_exceptions=False
    )
    assert payload.exit_code == 0
    data = json.loads(payload.output)
    assert data["links"] == []
    assert data["congested_count"] == 0
    assert data["next_steps"]
