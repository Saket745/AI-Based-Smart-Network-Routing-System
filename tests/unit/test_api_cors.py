"""Unit tests for secure CORS configuration in the API server and general settings."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nroute.core.config import GeneralConfig


def test_cors_default_origins_explicit() -> None:
    """Verify that by default, CORS origins do not include '*' and list explicit local origins."""
    config = GeneralConfig()
    assert "*" not in config.cors_origins
    assert "http://localhost:3000" in config.cors_origins
    assert "http://127.0.0.1:3000" in config.cors_origins


def test_cors_validation_rejects_wildcard() -> None:
    """Verify that Pydantic validation rejects '*' wildcard in cors_origins."""
    with pytest.raises(ValueError, match="is not allowed for cors_origins due to security risks"):
        GeneralConfig(cors_origins=["*"])

    with pytest.raises(ValueError, match="is not allowed for cors_origins due to security risks"):
        GeneralConfig(cors_origins=["http://localhost:3000", "*"])


def test_api_server_rejects_wildcard_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that if NROUTE_CORS_ORIGINS is set to '*' or contains '*', server.py raises a ValueError."""
    monkeypatch.setenv("NROUTE_CORS_ORIGINS", "*")

    # We patch nroute.core.config.load_config to raise an Exception so it falls back to environment variable processing
    with (
        patch(
            "nroute.core.config.load_config", side_effect=RuntimeError("Test Config Load Failure")
        ),
        pytest.raises(
            ValueError, match="is not allowed in NROUTE_CORS_ORIGINS due to security risks"
        ),
    ):
        # Re-importing or reloading the logic that defines _cors_origins
        import importlib

        import nroute.api.server

        importlib.reload(nroute.api.server)


def test_api_server_fallback_default_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that if NROUTE_CORS_ORIGINS is empty, server.py uses secure defaults on config failure."""
    monkeypatch.delenv("NROUTE_CORS_ORIGINS", raising=False)

    with patch(
        "nroute.core.config.load_config", side_effect=RuntimeError("Test Config Load Failure")
    ):
        import importlib

        import nroute.api.server

        importlib.reload(nroute.api.server)

        origins = nroute.api.server._cors_origins
        assert "*" not in origins
        assert "http://localhost:3000" in origins
        assert "http://127.0.0.1:3000" in origins


def test_api_server_valid_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that if NROUTE_CORS_ORIGINS has explicit safe origins, they are used."""
    monkeypatch.setenv("NROUTE_CORS_ORIGINS", "https://app.secure.com,https://api.secure.com")

    with patch(
        "nroute.core.config.load_config", side_effect=RuntimeError("Test Config Load Failure")
    ):
        import importlib

        import nroute.api.server

        importlib.reload(nroute.api.server)

        origins = nroute.api.server._cors_origins
        assert origins == ["https://app.secure.com", "https://api.secure.com"]
