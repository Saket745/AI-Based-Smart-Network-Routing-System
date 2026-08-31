"""Unit tests for the FastAPI API server endpoints, focusing on security (authentication and path traversal)."""
"""Unit tests for FastAPI API server authentication and path traversal security."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import nroute.api.server
from nroute.api.server import _FALLBACK_TOKEN, app
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


# ── Path Traversal Tests (with Authentication) ──


def test_api_load_topology_success_cwd(client: TestClient) -> None:
    """Test loading a valid topology from within the current working directory."""
    topo = Topology()
    topo.add_node("R1", type="router")
    topo.add_node("R2", type="router")
    topo.add_edge("R1", "R2", latency=5.0)

    temp_file = Path("test_topo_cwd.json")
    topo.save(temp_file)

    try:
        headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
        headers = {"Authorization": f"Bearer {nroute.api.server._FALLBACK_TOKEN}"}
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
    try:
        topo.save(temp_path)
    try:
        topo.save(temp_path)
    try:
        topo.save(temp_path)
    try:
        topo.save(temp_path)
    try:
        topo.save(temp_path)
        headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    try:
        topo.save(temp_path)
        headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    try:
        topo.save(temp_path)
    try:
        topo.save(temp_path)
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    try:
        topo.save(temp_path)
    topo.save(temp_path)
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    try:
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    try:
        topo.save(temp_path)
    try:
        topo.save(temp_path)
        headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    try:
        topo.save(temp_path)
        headers = {"Authorization": f"Bearer {nroute.api.server._FALLBACK_TOKEN}"}
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
    headers = {"Authorization": f"Bearer {nroute.api.server._FALLBACK_TOKEN}"}
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
