"""Unit tests for nroute twin CLI export feedback formatting."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nroute.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


def test_twin_impact_export_feedback(runner: CliRunner, tmp_path) -> None:
    """Test `nroute twin impact` formatted output when exporting to a JSON file."""
    topo_file = tmp_path / "topo.json"
    topo_file.write_text("{}")
    change_file = tmp_path / "change.json"
    change_file.write_text("{}")
    out_file = tmp_path / "impact.json"

    mock_result = MagicMock()
    mock_result.to_dict.return_value = {"impacted_pairs": [{"src": "a", "dst": "b"}]}

    with patch("nroute.simulation.digital_twin.DigitalTwinEngine") as mock_twin_cls:
        mock_twin = mock_twin_cls.return_value
        mock_twin.simulate_change.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "twin",
                "impact",
                "-t",
                str(topo_file),
                "-ch",
                str(change_file),
                "-o",
                str(out_file),
            ],
        )

        assert result.exit_code == 0
        assert "+" in result.output or "Successfully" in result.output
        assert "impacted pairs" in result.output
        assert out_file.exists()


def test_twin_rca_export_feedback(runner: CliRunner, tmp_path) -> None:
    """Test `nroute twin rca` formatted output when exporting to a JSON file."""
    topo_file = tmp_path / "topo.json"
    topo_file.write_text("{}")
    events_file = tmp_path / "events.json"
    events_file.write_text("[]")
    out_file = tmp_path / "rca.json"

    mock_result = MagicMock()
    mock_result.to_dict.return_value = {"root_causes": ["Node A failure"]}

    with patch("nroute.simulation.digital_twin.DigitalTwinEngine") as mock_twin_cls:
        mock_twin = mock_twin_cls.return_value
        mock_twin.diagnose.return_value = mock_result

        result = runner.invoke(
            cli,
            [
                "twin",
                "rca",
                "-t",
                str(topo_file),
                "-e",
                str(events_file),
                "-o",
                str(out_file),
            ],
        )

        assert result.exit_code == 0
        assert "+" in result.output or "Successfully" in result.output
        assert "root causes identified" in result.output
        assert out_file.exists()


def test_twin_reachability_export_feedback(runner: CliRunner, tmp_path) -> None:
    """Test `nroute twin reachability` formatted output when exporting to a JSON file."""
    topo_file = tmp_path / "topo.json"
    topo_file.write_text("{}")
    out_file = tmp_path / "reach.json"

    with patch("nroute.simulation.digital_twin.DigitalTwinEngine") as mock_twin_cls:
        mock_twin = mock_twin_cls.return_value
        mock_twin.compute_reachability.return_value = {"node1": {"node2", "node3"}}

        result = runner.invoke(
            cli,
            [
                "twin",
                "reachability",
                "-t",
                str(topo_file),
                "-o",
                str(out_file),
            ],
        )

        assert result.exit_code == 0
        assert "+" in result.output or "Successfully" in result.output
        assert "reachable pairs" in result.output
        assert out_file.exists()


def test_twin_audit_export_feedback(runner: CliRunner, tmp_path) -> None:
    """Test `nroute twin audit` formatted output when exporting to a JSON file."""
    log_file = tmp_path / "audit.ndjson"
    log_file.write_text(json.dumps({"action": "deploy"}) + "\n")
    out_file = tmp_path / "audit_out.json"

    result = runner.invoke(
        cli,
        [
            "twin",
            "audit",
            "-l",
            str(log_file),
            "-o",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    assert "+" in result.output or "Successfully" in result.output
    assert "1 records" in result.output
    assert out_file.exists()
