"""FastAPI backend for the Digital Twin web interface.

Minimal REST API exposing:
  * ``GET  /api/health``        — Network health summary
  * ``GET  /api/topology``      — Current topology as JSON
  * ``POST /api/config/ingest`` — Upload device configs
  * ``POST /api/impact``        — Simulate change and get blast-radius
  * ``POST /api/rca``           — Root-cause analysis
  * ``GET  /api/reachability``  — Pairwise reachability
  * ``GET  /api/audit``         — Audit trail
  * ``POST /api/topology/load`` — Load topology from file

Designed for SPA consumption with CORS enabled.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from nroute.core.openconfig import ConfigChange
from nroute.simulation.digital_twin import DigitalTwinEngine

# ── App factory ──────────────────────────────────────────────

app = FastAPI(
    title="NRoute Digital Twin API",
    description="Phase 1 — Deterministic Digital Twin Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance (per-process)
_engine: DigitalTwinEngine | None = None


def get_engine() -> DigitalTwinEngine:
    global _engine
    if _engine is None:
        _engine = DigitalTwinEngine(audit_log="./output/audit_trail.ndjson")
    return _engine


# ── Request / Response Models ────────────────────────────────


class TopologyLoadRequest(BaseModel):
    path: str


class ImpactRequest(BaseModel):
    change: dict[str, Any]
    weight: str = "latency"


class RCARequest(BaseModel):
    events: list[dict[str, Any]]


# ── Endpoints ────────────────────────────────────────────────


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Return network health summary."""
    engine = get_engine()
    try:
        return engine.health_summary()
    except RuntimeError:
        return {
            "status": "no_topology",
            "message": "No topology loaded. POST /api/topology/load first.",
        }


@app.post("/api/topology/load")
def load_topology(req: TopologyLoadRequest) -> dict[str, Any]:
    """Load a topology from a file path."""
    engine = get_engine()
    p = Path(req.path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {req.path}")
    try:
        topo = engine.load_topology(p)
        return {
            "status": "ok",
            "nodes": topo.node_count,
            "edges": topo.edge_count,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/topology")
def get_topology() -> dict[str, Any]:
    """Return the current topology as JSON."""
    engine = get_engine()
    try:
        return engine.topology.to_dict()
    except RuntimeError:
        raise HTTPException(
            status_code=400, detail="No topology loaded."
        )


@app.post("/api/config/ingest")
async def ingest_config(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload and ingest a device config file."""
    engine = get_engine()
    content = await file.read()

    # Write to a temp file for the parser
    suffix = Path(file.filename or "config.yaml").suffix
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=suffix, delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        hostnames = engine.ingest_config(tmp_path)
        return {
            "status": "ok",
            "devices_applied": hostnames,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/api/impact")
def simulate_impact(req: ImpactRequest) -> dict[str, Any]:
    """Simulate a change and return blast-radius report."""
    engine = get_engine()
    try:
        change = ConfigChange.model_validate(req.change)
        result = engine.simulate_change(change, weight=req.weight)
        return result.to_dict()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/rca")
def run_rca(req: RCARequest) -> dict[str, Any]:
    """Run root-cause analysis on provided events."""
    from nroute.simulation.rca import (
        EventCategory,
        EventSeverity,
        NetworkEvent,
        classify_event,
    )

    engine = get_engine()
    events: list[NetworkEvent] = []
    for idx, item in enumerate(req.events):
        cat = item.get("category", "unknown")
        sev = item.get("severity", "info")
        evt = NetworkEvent(
            event_id=str(item.get("event_id", f"evt_{idx}")),
            timestamp=float(item.get("timestamp", idx)),
            node_id=str(item.get("node_id", "")),
            interface=str(item.get("interface", "")),
            peer_node=str(item.get("peer_node", "")),
            event_type=str(item.get("event_type", "")),
            category=EventCategory(cat) if cat in [e.value for e in EventCategory] else EventCategory.UNKNOWN,
            severity=EventSeverity(sev) if sev in [e.value for e in EventSeverity] else EventSeverity.INFO,
            message=str(item.get("message", "")),
            raw=item,
        )
        events.append(classify_event(evt))

    try:
        result = engine.diagnose(events)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/reachability")
def get_reachability() -> dict[str, Any]:
    """Compute pairwise reachability matrix."""
    engine = get_engine()
    try:
        reach = engine.compute_reachability()
        return {k: sorted(v) for k, v in reach.items()}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/audit")
def get_audit(
    action: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return the audit trail."""
    engine = get_engine()
    from nroute.audit import AuditAction

    records = engine.audit.records

    if action:
        try:
            action_enum = AuditAction(action)
            records = [r for r in records if r.action == action_enum]
        except ValueError:
            pass

    if limit:
        records = records[:limit]

    return {
        "total": len(records),
        "records": [r.to_dict() for r in records],
    }
