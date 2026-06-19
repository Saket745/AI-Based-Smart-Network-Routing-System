"""Unit tests for nroute.utils.validators."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from nroute.exceptions import ValidationError
from nroute.utils.validators import (
    validate_file_path,
    validate_node_id,
    validate_positive_float,
    validate_probability,
)

# ---------------------------------------------------------------------------
# validate_node_id
# ---------------------------------------------------------------------------


def test_validate_node_id_valid_string() -> None:
    assert validate_node_id("R1") == "R1"


def test_validate_node_id_strips_whitespace() -> None:
    assert validate_node_id("  node1  ") == "node1"


def test_validate_node_id_int_coerced_to_string() -> None:
    assert validate_node_id(42) == "42"


def test_validate_node_id_float_coerced_to_string() -> None:
    result = validate_node_id(3.0)
    assert result == "3.0"


def test_validate_node_id_empty_string_raises() -> None:
    with pytest.raises(ValidationError, match="empty or whitespace"):
        validate_node_id("   ")


def test_validate_node_id_non_string_raises() -> None:
    with pytest.raises(ValidationError, match="must be a string"):
        validate_node_id(["list"])


# ---------------------------------------------------------------------------
# validate_positive_float
# ---------------------------------------------------------------------------


def test_validate_positive_float_valid() -> None:
    assert validate_positive_float(5.5, "latency") == pytest.approx(5.5)


def test_validate_positive_float_zero_allowed() -> None:
    assert validate_positive_float(0, "bw") == pytest.approx(0.0)


def test_validate_positive_float_string_numeric() -> None:
    assert validate_positive_float("3.14", "pi") == pytest.approx(3.14)


def test_validate_positive_float_negative_raises() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        validate_positive_float(-1.0, "latency")


def test_validate_positive_float_non_numeric_raises() -> None:
    with pytest.raises(ValidationError, match="must be a number"):
        validate_positive_float("bad", "x")


# ---------------------------------------------------------------------------
# validate_probability
# ---------------------------------------------------------------------------


def test_validate_probability_valid_range() -> None:
    assert validate_probability(0.0) == pytest.approx(0.0)
    assert validate_probability(0.5) == pytest.approx(0.5)
    assert validate_probability(1.0) == pytest.approx(1.0)


def test_validate_probability_out_of_range_raises() -> None:
    with pytest.raises(ValidationError, match=r"between 0\.0 and 1\.0"):
        validate_probability(1.1)
    with pytest.raises(ValidationError, match=r"between 0\.0 and 1\.0"):
        validate_probability(-0.1)


def test_validate_probability_non_numeric_raises() -> None:
    with pytest.raises(ValidationError, match="must be a number"):
        validate_probability("high")


# ---------------------------------------------------------------------------
# validate_file_path
# ---------------------------------------------------------------------------


def test_validate_file_path_existing_file() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        tmp = Path(f.name)
    result = validate_file_path(tmp, must_exist=True)
    assert result == tmp.resolve()
    tmp.unlink()


def test_validate_file_path_must_not_exist_mode() -> None:
    result = validate_file_path("/nonexistent/path/file.txt", must_exist=False)
    assert isinstance(result, Path)


def test_validate_file_path_missing_raises() -> None:
    with pytest.raises(ValidationError, match="does not exist"):
        validate_file_path("/nonexistent/path/file.txt", must_exist=True)


def test_validate_file_path_empty_raises() -> None:
    with pytest.raises(ValidationError, match="empty"):
        validate_file_path("", must_exist=False)
