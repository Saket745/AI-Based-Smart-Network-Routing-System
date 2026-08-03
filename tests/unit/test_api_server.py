"""Unit tests for the FastAPI API server endpoints, focusing on security and path traversal."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nroute.api.server import app
from nroute.core.topology import Topology


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_load_topology_success_cwd(client: TestClient) -> None:
    """Test loading a valid topology from within the current working directory."""
    topo = Topology()
    topo.add_node("R1", type="router")
    topo.add_node("R2", type="router")
    topo.add_edge("R1", "R2", latency=5.0)

    # Let's save it relative to cwd
    temp_file = Path("test_topo_cwd.json")
    topo.save(temp_file)

    try:
        response = client.post("/api/topology/load", json={"path": str(temp_file)})
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

    try:
        topo.save(temp_path)
        response = client.post("/api/topology/load", json={"path": str(temp_path)})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["nodes"] == 1
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_api_load_topology_not_found(client: TestClient) -> None:
    """Test loading a non-existent file inside the allowed directory returns 404."""
    response = client.post("/api/topology/load", json={"path": "non_existent_file_xyz.json"})
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]


def test_api_load_topology_outside_cwd_relative(client: TestClient) -> None:
    """Test relative path traversal outside the allowed directories returns 403."""
    response = client.post("/api/topology/load", json={"path": "../../etc/passwd"})
    assert response.status_code == 403
    assert "Access denied: Path is outside allowed directories" in response.json()["detail"]


def test_api_load_topology_outside_cwd_absolute(client: TestClient) -> None:
    """Test absolute path traversal outside the allowed directories returns 403."""
    response = client.post("/api/topology/load", json={"path": "/etc/passwd"})
    assert response.status_code == 403
    assert "Access denied: Path is outside allowed directories" in response.json()["detail"]
