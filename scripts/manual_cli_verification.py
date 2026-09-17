import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import networkx as nx
from fastapi.testclient import TestClient

from nroute.api.server import _FALLBACK_TOKEN, app
from nroute.core.topology import Topology


def _build_test_network() -> Topology:
    g = nx.DiGraph()
    for n in ["core0", "core1", "agg0", "agg1", "edge0", "edge1"]:
        g.add_node(n, capacity=1000.0, status="up", type="router")
    edges = [
        ("edge0", "agg0", 1000.0, 2.0),
        ("edge0", "agg1", 1000.0, 2.0),
        ("agg0", "edge0", 1000.0, 2.0),
        ("agg1", "edge0", 1000.0, 2.0),
        ("agg0", "core0", 1000.0, 5.0),
        ("agg0", "core1", 1000.0, 10.0),
        ("agg1", "core0", 1000.0, 10.0),
        ("agg1", "core1", 1000.0, 5.0),
        ("core0", "agg0", 1000.0, 5.0),
        ("core1", "agg0", 1000.0, 10.0),
        ("core0", "agg1", 1000.0, 10.0),
        ("core1", "agg1", 1000.0, 5.0),
        ("core0", "edge1", 1000.0, 5.0),
        ("edge1", "core0", 1000.0, 5.0),
        ("core1", "edge1", 1000.0, 5.0),
        ("edge1", "core1", 1000.0, 5.0),
    ]
    for u, v, bw, lat in edges:
        g.add_edge(u, v, bandwidth=bw, latency=lat, utilization=0.10, packet_loss=0.0, status="up", weight=lat)
    return Topology(g)


def main():
    print("=" * 80)
    print("MANUAL PRE-FLIGHT VALIDATION VERIFICATION (CLI & REST)")
    print("=" * 80)

    tmp_dir = Path("artifacts/manual_verify")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    topo = _build_test_network()
    topo_path = tmp_dir / "topo.json"
    topo_path.write_text(json.dumps(topo.to_dict(), indent=2))

    # 1. PASS fixture
    change_pass = tmp_dir / "change_pass.json"
    change_pass.write_text(json.dumps({
        "change_id": "CHG-PASS-001",
        "description": "Non-disruptive capacity upgrade",
        "link_changes": [{"src": "agg0", "dst": "core0", "bandwidth": 2000.0}],
    }, indent=2))

    # 2. WARN fixture
    change_warn = tmp_dir / "change_warn.json"
    change_warn.write_text(json.dumps({
        "change_id": "CHG-WARN-002",
        "description": "Primary link cut with alternative path available",
        "link_changes": [{"src": "agg0", "dst": "core0", "status": "down"}],
    }, indent=2))

    policy_warn = tmp_dir / "policy.json"
    policy_warn.write_text(json.dumps({
        "max_latency_increase_warn_ms": 3.0,
        "max_latency_increase_block_ms": 20.0,
        "max_path_changed_ratio_warn": 0.50,
    }, indent=2))

    # 3. BLOCK fixture
    change_block = tmp_dir / "change_block.json"
    change_block.write_text(json.dumps({
        "change_id": "CHG-BLOCK-003",
        "description": "Partition graph by isolating edge1",
        "link_changes": [
            {"src": "core0", "dst": "edge1", "status": "down"},
            {"src": "core1", "dst": "edge1", "status": "down"},
        ],
    }, indent=2))

    # CLI Test A: PASS
    print("\n>>> [1] CLI Invocations: PASS")
    p1 = subprocess.run(
        [sys.executable, "-m", "nroute.cli.main", "twin", "validate", "-t", str(topo_path), "-ch", str(change_pass)],
        capture_output=True, text=True,
    )
    print(f"Exit Code: {p1.returncode}")
    print(p1.stdout)
    assert p1.returncode == 0

    # CLI Test B: WARN (default exit 0)
    print("\n>>> [2] CLI Invocations: WARN (Permissive default)")
    p2 = subprocess.run(
        [sys.executable, "-m", "nroute.cli.main", "twin", "validate", "-t", str(topo_path), "-ch", str(change_warn), "-p", str(policy_warn)],
        capture_output=True, text=True,
    )
    print(f"Exit Code: {p2.returncode}")
    print(p2.stdout)
    assert p2.returncode == 0

    # CLI Test C: WARN (strict exit 2)
    print("\n>>> [3] CLI Invocations: WARN (--strict-warnings)")
    p3 = subprocess.run(
        [sys.executable, "-m", "nroute.cli.main", "twin", "validate", "-t", str(topo_path), "-ch", str(change_warn), "-p", str(policy_warn), "--strict-warnings"],
        capture_output=True, text=True,
    )
    print(f"Exit Code: {p3.returncode}")
    print(p3.stdout)
    assert p3.returncode == 2

    # CLI Test D: BLOCK (exit 1)
    print("\n>>> [4] CLI Invocations: BLOCK")
    p4 = subprocess.run(
        [sys.executable, "-m", "nroute.cli.main", "twin", "validate", "-t", str(topo_path), "-ch", str(change_block)],
        capture_output=True, text=True,
    )
    print(f"Exit Code: {p4.returncode}")
    print(p4.stdout)
    assert p4.returncode == 1

    # CLI Test E: JSON Mode
    print("\n>>> [5] CLI Invocations: JSON mode")
    p5 = subprocess.run(
        [sys.executable, "-m", "nroute.cli.main", "twin", "validate", "-t", str(topo_path), "-ch", str(change_pass), "--json"],
        capture_output=True, text=True,
    )
    print(f"Exit Code: {p5.returncode}")
    parsed = json.loads(p5.stdout)
    print(json.dumps(parsed, indent=2))
    assert parsed["verdict"] == "PASS"

    # REST Test: POST /api/twin/validate
    print("\n>>> [6] REST API Invocations: POST /api/twin/validate")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_FALLBACK_TOKEN}"}
    client.post("/api/topology/load", json={"path": str(topo_path)}, headers=headers)

    res_api = client.post(
        "/api/twin/validate",
        json={"change": json.loads(change_warn.read_text()), "policy": json.loads(policy_warn.read_text())},
        headers=headers,
    )
    print(f"HTTP Status: {res_api.status_code}")
    api_body = res_api.json()
    print(f"Verdict: {api_body['verdict']}")
    print(f"Summary: {api_body['summary']}")
    print(f"Warning Violations: {api_body['warning_violations']}")
    assert res_api.status_code == 200
    assert api_body["verdict"] == "WARN"

    print("\n" + "=" * 80)
    print("ALL MANUAL VERIFICATIONS PASSED WITH 100% CONTRACT FIDELITY!")
    print("=" * 80)


if __name__ == "__main__":
    main()
