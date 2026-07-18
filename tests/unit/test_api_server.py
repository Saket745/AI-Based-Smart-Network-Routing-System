"""Unit tests for FastAPI API server authentication."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nroute.api.server import _FALLBACK_TOKEN, app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_docs_and_openapi_unauthenticated(client: TestClient) -> None:
    """Accessing docs and openapi schema should NOT require authentication."""
    response = client.get("/docs")
    assert response.status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200


def test_api_endpoints_require_authentication_by_default(client: TestClient) -> None:
    """API endpoints must return 401 if unauthenticated and no custom token is configured."""
    # Since no environment variable/config token is set in standard test runtime,
    # it uses the secure _FALLBACK_TOKEN. Therefore, no-token request must fail.
    response = client.get("/api/health")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_api_endpoints_fail_with_invalid_token(client: TestClient) -> None:
    """API endpoints must return 401 when an invalid token is provided."""
    headers = {"Authorization": "Bearer invalid_secret_token_123"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 401


def test_api_endpoints_succeed_with_configured_env_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API endpoints must succeed when a valid token is configured via environment."""
    test_token = "my_super_secret_test_token"
    monkeypatch.setenv("NROUTE_API_TOKEN", test_token)

    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "no_topology"


def test_api_endpoints_succeed_with_configured_config_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API endpoints must succeed when a valid token is configured via config."""
    # We mock load_config to return a config where general.api_token is set
    from nroute.core.config import GeneralConfig, NRouteConfig

    test_token = "config_secret_token"
    mock_config = NRouteConfig(general=GeneralConfig(api_token=test_token))

    import nroute.api.server

    monkeypatch.setattr(nroute.api.server, "load_config", lambda: mock_config)

    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "no_topology"


def test_fallback_token_usage(client: TestClient) -> None:
    """If no custom token is configured, the server falls back to _FALLBACK_TOKEN."""
    # Since _FALLBACK_TOKEN is generated on startup and we did not set env/config,
    # providing _FALLBACK_TOKEN must succeed.
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "no_topology"
