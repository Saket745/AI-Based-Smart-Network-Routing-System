"""Unit tests for the FastAPI API server endpoints, focusing on security (authentication, CORS, and path traversal)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import nroute.api.server
from nroute.api.server import _FALLBACK_TOKEN, app
from nroute.core.config import DEFAULT_CORS_ORIGINS, load_config
from nroute.core.topology import Topology


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ── Authentication Tests ──


def test_docs_and_openapi_unauthenticated(client: TestClient) -> None:
    """Accessing docs and openapi schema should NOT require authentication."""
    response = client.get("/docs")
    assert response.status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200


def test_api_endpoints_require_authentication_by_default(client: TestClient) -> None:
    """API endpoints must return 401 if unauthenticated and no custom token is configured."""
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


def test_api_security_headers(client: TestClient) -> None:
    """API responses must include defense-in-depth security headers."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_api_endpoints_succeed_with_configured_config_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API endpoints must succeed when a valid token is configured via config."""
    from nroute.core.config import GeneralConfig, NRouteConfig

    test_token = "config_secret_token"
    mock_config = NRouteConfig(general=GeneralConfig(api_token=test_token))

    monkeypatch.setattr(nroute.api.server, "load_config", lambda: mock_config)

    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "no_topology"


def test_fallback_token_usage(client: TestClient) -> None:
    """If no custom token is configured, the server falls back to _FALLBACK_TOKEN."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "no_topology"


# ── CORS Security Tests ──


def test_cors_origins_rejection_and_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure that '*' and empty values are rejected, and default to secure origins."""
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("NROUTE_GENERAL_CORS_ORIGINS", "*")
    cfg = load_config()
    assert cfg.general.cors_origins == DEFAULT_CORS_ORIGINS

    monkeypatch.setenv("NROUTE_GENERAL_CORS_ORIGINS", "")
    cfg = load_config()
    assert cfg.general.cors_origins == DEFAULT_CORS_ORIGINS

    monkeypatch.setenv("NROUTE_GENERAL_CORS_ORIGINS", "http://good.com,*,  , http://also-good.com")
    cfg = load_config()
    assert cfg.general.cors_origins == ["http://good.com", "http://also-good.com"]


def test_api_server_cors_middleware_initialization() -> None:
    """Ensure API server initializes CORSMiddleware with secure origins."""
    for middleware in app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            origins = middleware.kwargs.get("allow_origins", [])
            assert "*" not in origins
            assert "" not in origins
            assert len(origins) > 0
            for origin in origins:
                assert origin.startswith("http")


def test_api_responses_include_security_headers(client: TestClient) -> None:
    """API responses must include defense-in-depth HTTP security headers."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.get("/api/health", headers=headers)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


# ── Path Traversal Tests (with Authentication) ──


def test_api_load_topology_success_cwd(client: TestClient) -> None:
    """Test loading a valid topology from within the current working directory."""
    topo = Topology()
    topo.add_node("R1", type="router")
    topo.add_node("R2", type="router")
    topo.add_edge("R1", "R2", latency=5.0)

    temp_file = Path("test_topo_cwd.json")
    topo.save(temp_file)

    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    try:
        response = client.post("/api/topology/load", json={"path": str(temp_file)}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["nodes"] == 2
        assert data["edges"] == 1
    finally:
        if temp_file.exists():
            temp_file.unlink()


def test_api_load_topology_success_temp(client: TestClient) -> None:
    """Test loading a valid topology from within the temp directory."""
    topo = Topology()
    topo.add_node("R1", type="router")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        temp_path = Path(f.name)

    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    try:
        topo.save(temp_path)
        response = client.post("/api/topology/load", json={"path": str(temp_path)}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["nodes"] == 1
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_api_load_topology_not_found(client: TestClient) -> None:
    """Test loading a non-existent file inside the allowed directory returns 404."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.post(
        "/api/topology/load", json={"path": "non_existent_file_xyz.json"}, headers=headers
    )
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]


def test_api_load_topology_outside_cwd_relative(client: TestClient) -> None:
    """Test relative path traversal outside the allowed directories returns 403."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.post("/api/topology/load", json={"path": "../../etc/passwd"}, headers=headers)
    assert response.status_code == 403
    assert "Access denied: Path is outside allowed directories" in response.json()["detail"]


def test_api_load_topology_outside_cwd_absolute(client: TestClient) -> None:
    """Test absolute path traversal outside the allowed directories returns 403."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.post("/api/topology/load", json={"path": "/etc/passwd"}, headers=headers)
    assert response.status_code == 403
    assert "Access denied: Path is outside allowed directories" in response.json()["detail"]


def test_api_config_ingest_file_size_limit(client: TestClient) -> None:
    """Verify that uploading a file larger than 5MB returns 413 Payload Too Large."""
    headers = {
        "Authorization": f"Bearer {_FALLBACK_TOKEN}",
        "Content-Length": str(6 * 1024 * 1024),
    }

    response = client.post(
        "/api/config/ingest",
        files={"file": ("config.yaml", b"dummy")},
        headers=headers,
    )
    assert response.status_code == 413
    assert "exceeds maximum limit" in response.json()["detail"]

    large_content = b"a" * (5 * 1024 * 1024 + 10)
    response = client.post(
        "/api/config/ingest",
        files={"file": ("config.yaml", large_content)},
        headers={"Authorization": f"Bearer {_FALLBACK_TOKEN}"},
    )
    assert response.status_code == 413
    assert "exceeds maximum limit" in response.json()["detail"]


def test_load_topology_path_traversal_rejected(client: TestClient) -> None:
    """Verify that path traversal attempts with ../ are explicitly rejected with HTTP 403."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.post(
        "/api/topology/load", json={"path": "../../../etc/shadow"}, headers=headers
    )
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_load_topology_nonexistent_path(client: TestClient) -> None:
    """Verify that loading a non-existent topology within valid directory returns 404."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.post(
        "/api/topology/load", json={"path": "missing_topology_file_12345.json"}, headers=headers
    )
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]


def test_load_topology_null_byte_path_rejected(client: TestClient) -> None:
    """Verify that paths containing null bytes or invalid characters return HTTP 400."""
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    response = client.post(
        "/api/topology/load", json={"path": "topology.json\0.txt"}, headers=headers
    )
    assert response.status_code == 400
    assert "null bytes" in response.json()["detail"]


# ── Active Token Discovery Tests ──


def test_get_active_api_token_configured_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_active_api_token returns configured token and is_fallback=False when env var is set."""
    from nroute.api.server import get_active_api_token

    monkeypatch.setenv("NROUTE_API_TOKEN", "test_env_token_456")
    token, is_fallback = get_active_api_token()
    assert token == "test_env_token_456"
    assert is_fallback is False


def test_get_active_api_token_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_active_api_token returns _FALLBACK_TOKEN and is_fallback=True when unset."""
    from nroute.api.server import _FALLBACK_TOKEN, get_active_api_token

    monkeypatch.delenv("NROUTE_API_TOKEN", raising=False)
    monkeypatch.delenv("NROUTE_GENERAL_API_TOKEN", raising=False)
    token, is_fallback = get_active_api_token()
    assert token == _FALLBACK_TOKEN
    assert is_fallback is True


def test_api_start_cli_displays_fallback_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """nroute api start prints generated session token when no token is configured."""
    from click.testing import CliRunner

    from nroute.cli.api_cmd import api_cmd

    monkeypatch.delenv("NROUTE_API_TOKEN", raising=False)
    monkeypatch.delenv("NROUTE_GENERAL_API_TOKEN", raising=False)

    # Mock uvicorn.run so it doesn't actually block starting a server
    called_with: dict[str, Any] = {}

    def mock_run(app_str: str, host: str, port: int, log_level: str) -> None:
        called_with.update({"app": app_str, "host": host, "port": port, "log_level": log_level})

    monkeypatch.setattr("uvicorn.run", mock_run)

    runner = CliRunner()
    result = runner.invoke(api_cmd, ["start", "--host", "127.0.0.1", "--port", "8000"])
    assert result.exit_code == 0
    assert "Generated local session token:" in result.output
    assert "Bearer " in result.output
    assert called_with["host"] == "127.0.0.1"
    assert called_with["port"] == 8000
