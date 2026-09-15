import json
import logging
from typing import Optional
from fastapi import WebSocket
from ..schema.ws import WsEnvelope, WsType
from ..schema.events import AgentEvent
from ..bus.bus import EventBus

logger = logging.getLogger("agentsentrix.server.ws")

class ConnectionManager:
    """
    WebSocket connection manager handling real-time telemetry broadcasts,
    client subscriptions, and reconnection catchup streams via bus.get_since(seq).
    """

    def __init__(self, bus: Optional[EventBus] = None) -> None:
        self.bus = bus
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, since: Optional[int] = None) -> None:
        """Accept a new WebSocket connection and push catchup events if requested."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[WebSocket] Client connected. Total active connections: {len(self.active_connections)}")

        # Send initial HELLO envelope
        hello_env = WsEnvelope(type=WsType.HELLO, data={"msg": "Connected to AgentSentrix Real-Time Stream", "status": "online"})
        await websocket.send_text(hello_env.model_dump_json())

        # If client reconnected with ?since=<seq>, send catchup events
        if since is not None and self.bus:
            missed_events = self.bus.get_since(since)
            logger.info(f"[WebSocket] Reconnection catchup requested for seq > {since}. Sending {len(missed_events)} events.")
            for evt in missed_events:
                env = WsEnvelope(type=WsType.EVENT, data=evt.model_dump(mode="json"))
                await websocket.send_text(env.model_dump_json())

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"[WebSocket] Client disconnected. Total active connections: {len(self.active_connections)}")

    async def broadcast(self, envelope: WsEnvelope) -> None:
        """Broadcast a WsEnvelope to all connected WebSocket clients."""
        if not self.active_connections:
            return

        payload_str = envelope.model_dump_json()
        disconnected: list[WebSocket] = []

        for ws in list(self.active_connections):
            try:
                await ws.send_text(payload_str)
            except Exception as exc:
                logger.warning(f"[WebSocket] Error broadcasting to client: {exc}")
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def on_event(self, event: AgentEvent) -> None:
        """Bus subscriber callback that converts incoming AgentEvent to WsEnvelope and broadcasts to UI."""
        envelope = WsEnvelope(type=WsType.EVENT, data=event.model_dump(mode="json"))
        await self.broadcast(envelope)
