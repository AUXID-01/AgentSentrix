import json
import logging
from typing import Optional, Any
from fastapi import APIRouter, Request, Query, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..schema.enums import Verdict
from ..schema.ws import WsEnvelope, WsType
from ..schema.events import DecisionUpdate

logger = logging.getLogger("agentsentrix.server.routes")

router = APIRouter()

class DecisionRequest(BaseModel):
    event_id: str
    verdict: Verdict
    note: Optional[str] = None
    decided_by: str = "operator"

@router.get("/health")
async def get_health(request: Request) -> dict[str, Any]:
    """Health check endpoint verifying Redis, DuckDB, and EventBus status."""
    bus = getattr(request.app.state, "bus", None)
    cache = getattr(request.app.state, "cache", None)
    duckdb_sink = getattr(request.app.state, "duckdb_sink", None)

    redis_ok = cache.is_redis_connected() if cache else False
    bus_seq = bus.current_seq if bus else 0

    duckdb_count = 0
    if duckdb_sink and hasattr(duckdb_sink, "con") and duckdb_sink.con:
        try:
            res = duckdb_sink.con.execute("SELECT count(*) FROM events").fetchone()
            duckdb_count = res[0] if res else 0
        except Exception as exc:
            logger.warning(f"Error querying DuckDB count in /health: {exc}")

    logger.info(f"[REST] /health called -> Status: Healthy (Redis: {redis_ok}, DuckDB count: {duckdb_count}, Bus Seq: {bus_seq})")

    return {
        "status": "healthy",
        "redis": redis_ok,
        "redis_connected": redis_ok,
        "duckdb": duckdb_count > 0 or (duckdb_sink is not None),
        "duckdb_event_count": duckdb_count,
        "bus_current_seq": bus_seq
    }

@router.post("/events/ingest")
async def ingest_event(request: Request, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Ingest external AgentEvent telemetry from simulation runner or sensors into active server pipeline."""
    bus = getattr(request.app.state, "bus", None)
    if not bus:
        raise HTTPException(status_code=500, detail="EventBus unavailable on server")
    
    try:
        from ..schema.events import AgentEvent
        event = AgentEvent.model_validate(event_dict)
        await bus.publish(event)
        logger.info(f"[REST] /events/ingest -> Event '{event.id}' ingested successfully.")
        return {"status": "ingested", "event_id": event.id, "seq": event.seq}
    except Exception as exc:
        logger.error(f"[REST] /events/ingest validation/publish error: {exc}")
        raise HTTPException(status_code=400, detail=f"Failed to ingest event: {exc}")

@router.get("/events")
async def get_events(
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session_id: Optional[str] = Query(None)
) -> dict[str, Any]:
    """Fetch paginated event history from DuckDB analytical storage."""
    duckdb_sink = getattr(request.app.state, "duckdb_sink", None)
    if not duckdb_sink or not hasattr(duckdb_sink, "con") or not duckdb_sink.con:
        return {"events": [], "count": 0, "limit": limit, "offset": offset}

    try:
        if session_id:
            query = "SELECT payload_json FROM events WHERE session_id = ? ORDER BY seq DESC LIMIT ? OFFSET ?"
            params = [session_id, limit, offset]
            count_query = "SELECT count(*) FROM events WHERE session_id = ?"
            count_params = [session_id]
        else:
            query = "SELECT payload_json FROM events ORDER BY seq DESC LIMIT ? OFFSET ?"
            params = [limit, offset]
            count_query = "SELECT count(*) FROM events"
            count_params = []

        total_count = duckdb_sink.con.execute(count_query, count_params).fetchone()[0]
        rows = duckdb_sink.con.execute(query, params).fetchall()

        events = []
        for r in rows:
            try:
                events.append(json.loads(r[0]))
            except Exception:
                pass

        logger.info(f"[REST] /events fetched {len(events)} events (total: {total_count})")
        return {
            "events": events,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }
    except Exception as exc:
        logger.error(f"[REST] /events error querying DuckDB: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query error: {exc}")

@router.get("/graph")
async def get_graph(
    request: Request,
    session_id: str = Query("default_session")
) -> dict[str, Any]:
    """Return the current topology projection snapshot (GraphSnapshot)."""
    projection = getattr(request.app.state, "projection", None)
    if not projection:
        return {"session_id": session_id, "nodes": [], "links": [], "seq": 0}

    snapshot = projection.get_snapshot(session_id)
    logger.info(f"[REST] /graph returned snapshot for '{session_id}' (Nodes: {len(snapshot.nodes)}, Links: {len(snapshot.links)})")
    return snapshot.model_dump(mode="json")

@router.post("/decide")
async def post_decide(request: Request, body: DecisionRequest) -> dict[str, Any]:
    """
    Accept operator decision (allowed or blocked) to resolve in-flight QuarantineManager futures.
    Broadcasts decision updates to connected WebSockets.
    """
    quarantine_mgr = getattr(request.app.state, "quarantine_mgr", None)
    ws_manager = getattr(request.app.state, "ws_manager", None)

    if not quarantine_mgr:
        raise HTTPException(status_code=500, detail="QuarantineManager unavailable.")

    resolved = quarantine_mgr.resolve_quarantine(body.event_id, body.verdict, note=body.note)

    # Broadcast decision update via WebSocket
    if ws_manager:
        dec_update = DecisionUpdate(
            event_id=body.event_id,
            verdict=body.verdict,
            decided_by=body.decided_by,
            note=body.note
        )
        envelope = WsEnvelope(type=WsType.DECISION, data=dec_update.model_dump(mode="json"))
        await ws_manager.broadcast(envelope)

    # Log MLflow False-Positive / Human Override telemetry signal
    try:
        from ..analytics.mlflow_tracker import MLflowTracker
        tracker = MLflowTracker()
        verdict_str = body.verdict.value if hasattr(body.verdict, "value") else str(body.verdict)
        tracker.log_human_override(
            event_id=body.event_id,
            original_verdict="quarantined",
            new_verdict=verdict_str,
            note=body.note
        )
    except Exception as exc:
        logger.warning(f"[REST] Failed to log MLflow human override: {exc}")

    logger.info(f"[REST] /decide event '{body.event_id}' -> Verdict: {body.verdict.value} (Resolved: {resolved})")

    return {
        "success": resolved,
        "event_id": body.event_id,
        "verdict": body.verdict.value,
        "note": body.note
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, since: Optional[int] = Query(None)):
    """Real-time telemetry streaming endpoint supporting client reconnection catchups (?since=<seq>)."""
    ws_manager = getattr(websocket.app.state, "ws_manager", None)
    if not ws_manager:
        await websocket.close(code=1011, reason="WebSocket ConnectionManager not initialized")
        return

    await ws_manager.connect(websocket, since=since)
    try:
        while True:
            # Keep socket alive and listening for ping/pong or client messages
            data = await websocket.receive_text()
            logger.debug(f"[WebSocket] Received message from client: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning(f"[WebSocket] Exception on socket: {exc}")
        ws_manager.disconnect(websocket)
