"""Unit tests for secure CORS configuration and server initialization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nroute.api.server import app
from nroute.core.config import DEFAULT_CORS_ORIGINS, load_config

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_cors_origins_rejection_and_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure that '*' and empty values are rejected, and default to secure origins."""
    monkeypatch.chdir(tmp_path)

    # 1. Test raw "*" wildcard gets rejected and defaults
    monkeypatch.setenv("NROUTE_GENERAL_CORS_ORIGINS", "*")
    cfg = load_config()
    assert cfg.general.cors_origins == DEFAULT_CORS_ORIGINS

    # 2. Test empty string gets rejected and defaults
    monkeypatch.setenv("NROUTE_GENERAL_CORS_ORIGINS", "")
    cfg = load_config()
    assert cfg.general.cors_origins == DEFAULT_CORS_ORIGINS

    # 3. Test list containing wildcard or empty elements gets cleaned
    monkeypatch.setenv("NROUTE_GENERAL_CORS_ORIGINS", "http://good.com,*,  , http://also-good.com")
    cfg = load_config()
    assert cfg.general.cors_origins == ["http://good.com", "http://also-good.com"]


def test_api_server_cors_middleware_initialization() -> None:
    """Ensure API server initializes CORSMiddleware with secure origins."""
    # Verify that the list of origins in the CORSMiddleware does not contain '*' or empty strings.
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            origins = middleware.kwargs.get("allow_origins", [])
            assert "*" not in origins
            assert "" not in origins
            assert len(origins) > 0
            for origin in origins:
                assert origin.startswith("http")
