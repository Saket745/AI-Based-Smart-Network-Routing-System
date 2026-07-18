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

import asyncio
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nroute.core.config import load_config
from nroute.core.openconfig import ConfigChange
from nroute.simulation.digital_twin import DigitalTwinEngine

# ── App factory ──────────────────────────────────────────────

app = FastAPI(
    title="NRoute Digital Twin API",
    description="Phase 1 — Deterministic Digital Twin Platform",
    version="1.0.0",
)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Load CORS configuration
try:
    _cfg = load_config()
    _cors_origins = _cfg.general.cors_origins
except Exception:
    import os

    _cors_origins_raw = os.environ.get("NROUTE_CORS_ORIGINS", "")
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

# Filter out '*' and empty strings, ensure secure local development defaults as fallback
_cors_origins = [o for o in _cors_origins if o and o != "*"]
if not _cors_origins:
    _cors_origins = DEFAULT_CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance (per-process)
_engine: DigitalTwinEngine | None = None

# Thread pool for offloading CPU-bound simulation / graph operations
_executor = ThreadPoolExecutor(max_workers=4)


def get_engine() -> DigitalTwinEngine:
    global _engine
    if _engine is None:
        _engine = DigitalTwinEngine(audit_log="./output/audit_trail.ndjson")
    return _engine


async def _run_in_executor(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a blocking function in the thread pool executor.

    Prevents CPU-bound graph computations from blocking the ASGI event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, partial(func, *args, **kwargs))


# ── Request / Response Models ────────────────────────────────


class TopologyLoadRequest(BaseModel):
    path: str


class ImpactRequest(BaseModel):
    change: dict[str, Any]
    weight: str = "latency"


class NetworkEventInput(BaseModel):
    """Pydantic schema for a single network event in the RCA endpoint.

    Enforces type validation at the API boundary instead of raw dict parsing.
    """

    event_id: str = ""
    timestamp: float = 0.0
    node_id: str = ""
    interface: str = ""
    peer_node: str = ""
    event_type: str = ""
    category: str = Field(
        default="unknown", description="Event category: routing, interface, syslog, unknown"
    )
    severity: str = Field(
        default="info", description="Event severity: critical, error, warning, info"
    )
    message: str = ""


class RCARequest(BaseModel):
    events: list[NetworkEventInput]


# ── Endpoints ────────────────────────────────────────────────


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Return network health summary."""
    engine = get_engine()
    try:
        return cast("dict[str, Any]", await _run_in_executor(engine.health_summary))
    except RuntimeError:
        return {
            "status": "no_topology",
            "message": "No topology loaded. POST /api/topology/load first.",
        }


@app.post("/api/topology/load")
async def load_topology(req: TopologyLoadRequest) -> dict[str, Any]:
    """Load a topology from a file path."""
    engine = get_engine()
    p = Path(req.path).resolve()

    # Path traversal protection: restrict to allowed directories
    allowed_dirs = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(p.is_relative_to(d) for d in allowed_dirs):
        raise HTTPException(
            status_code=403, detail="Access denied: Path is outside allowed directories."
        )

    if not p.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {req.path}")
    try:
        topo = await _run_in_executor(engine.load_topology, p)
        return {
            "status": "ok",
            "nodes": topo.node_count,
            "edges": topo.edge_count,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/topology")
async def get_topology() -> dict[str, Any]:
    """Return the current topology as JSON."""
    engine = get_engine()
    try:
        return cast("dict[str, Any]", await _run_in_executor(engine.topology.to_dict))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail="No topology loaded.") from exc


@app.post("/api/config/ingest")
async def ingest_config(file: UploadFile = File(...)) -> dict[str, Any]:  # noqa: B008
    """Upload and ingest a device config file."""
    engine = get_engine()
    content = await file.read()

    # Write to a temp file for the parser
    suffix = Path(file.filename or "config.yaml").suffix
    with tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        hostnames = await _run_in_executor(engine.ingest_config, tmp_path)
        return {
            "status": "ok",
            "devices_applied": hostnames,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.post("/api/impact")
async def simulate_impact(req: ImpactRequest) -> dict[str, Any]:
    """Simulate a change and return blast-radius report."""
    engine = get_engine()
    try:
        change = ConfigChange.model_validate(req.change)
        result = await _run_in_executor(engine.simulate_change, change, weight=req.weight)
        return cast("dict[str, Any]", result.to_dict())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rca")
async def run_rca(req: RCARequest) -> dict[str, Any]:
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
        cat = item.category
        sev = item.severity
        evt = NetworkEvent(
            event_id=item.event_id or f"evt_{idx}",
            timestamp=item.timestamp if item.timestamp else float(idx),
            node_id=item.node_id,
            interface=item.interface,
            peer_node=item.peer_node,
            event_type=item.event_type,
            category=EventCategory(cat)
            if cat in [e.value for e in EventCategory]
            else EventCategory.UNKNOWN,
            severity=EventSeverity(sev)
            if sev in [e.value for e in EventSeverity]
            else EventSeverity.INFO,
            message=item.message,
            raw=item.model_dump(),
        )
        events.append(classify_event(evt))

    try:
        result = await _run_in_executor(engine.diagnose, events)
        return cast("dict[str, Any]", result.to_dict())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/reachability")
async def get_reachability() -> dict[str, Any]:
    """Compute pairwise reachability matrix."""
    engine = get_engine()
    try:
        reach = await _run_in_executor(engine.compute_reachability)
        return {k: sorted(v) for k, v in reach.items()}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/audit")
async def get_audit(
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
