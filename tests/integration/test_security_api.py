from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient
from src.nroute.api.server import app


def test_path_traversal_vulnerability():
    client = TestClient(app)

    # Create a sensitive file outside the expected directory
    # For this test, we'll try to access pyproject.toml which is in the root
    # assuming the server might be running in a way where it expects data elsewhere
    # OR we just try to go up from the current directory.

    # Create a file outside the current directory
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(b'{"nodes": [], "edges": []}')
        tmp_path = tmp.name

    try:
        print(f"CWD: {os.getcwd()}")
        print(f"Temp file: {tmp_path}")

        # This path is definitely outside CWD
        # If it's vulnerable, it will return 200 (ok) because it's a valid empty topology.
        response = client.post("/api/topology/load", json={"path": tmp_path})

        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")

        # Fixed: returns 403 Forbidden
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

        # Test valid path (within CWD)
        # Create a temp file inside CWD
        valid_path = Path("test_topo_safe.json").resolve()
        valid_path.write_text('{"nodes": [], "edges": []}')
        try:
            response = client.post("/api/topology/load", json={"path": str(valid_path)})
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
        finally:
            if valid_path.exists():
                valid_path.unlink()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
