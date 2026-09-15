import asyncio
import logging
from typing import Any, Optional
from ..schema.enums import Verdict
from ..bus.cache import StateCache

logger = logging.getLogger("agentsentrix.proxy.quarantine")

class QuarantineManager:
    """
    Manages in-flight quarantined MCP tool calls awaiting human approval.
    Synchronizes pending and resolved quarantine states with Redis StateCache.
    """

    def __init__(self, cache: Optional[StateCache] = None) -> None:
        self.cache = cache
        self.pending_futures: dict[str, asyncio.Future[dict[str, Any]]] = {}

    def create_quarantine_future(self, event_id: str, event_data: Optional[dict[str, Any]] = None) -> asyncio.Future[dict[str, Any]]:
        """Create and store an asyncio.Future for a quarantined event and sync to StateCache."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self.pending_futures[event_id] = future
        logger.info(f"Created quarantine future for event_id: {event_id}")

        # Synchronize pending quarantine state with Redis / StateCache
        if self.cache:
            data = {
                "status": "quarantined",
                "event_id": event_id,
            }
            if event_data:
                data.update(event_data)
            self.cache.set_quarantine(event_id, data)

        return future

    def resolve_quarantine(self, event_id: str, verdict: Verdict, note: Optional[str] = None) -> bool:
        """
        Resolves a pending quarantine future with a decision verdict (ALLOWED or BLOCKED).
        Unblocks the suspended MCP tool invocation and updates StateCache.
        """
        if event_id in self.pending_futures:
            future = self.pending_futures.pop(event_id)
            if not future.done():
                future.set_result({"verdict": verdict, "note": note})
                logger.info(f"Resolved quarantine for {event_id} with verdict: {verdict}")

                # Update state in Redis / StateCache
                if self.cache:
                    existing_data = self.cache.get_quarantine(event_id) or {}
                    existing_data.update({
                        "status": "resolved",
                        "verdict": verdict.value if hasattr(verdict, "value") else str(verdict),
                        "note": note
                    })
                    self.cache.set_quarantine(event_id, existing_data)

                return True

        logger.warning(f"No pending quarantine future found for event_id: {event_id}")
        return False
