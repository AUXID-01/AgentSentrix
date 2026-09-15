import asyncio
import logging
from collections import deque
from typing import Callable, Any, Awaitable
from .sinks.base import Sink
from ..schema.events import AgentEvent

logger = logging.getLogger("agentsentrix.bus")

SubscriberType = Sink | Callable[[AgentEvent], Awaitable[Any]]

class EventBus:
    """In-memory pub/sub event bus with monotonic sequence counter and ring buffer."""

    def __init__(self, maxlen: int = 1000) -> None:
        self.ring_buffer: deque[AgentEvent] = deque(maxlen=maxlen)
        self._seq: int = 0
        self._subscribers: list[SubscriberType] = []

    @property
    def current_seq(self) -> int:
        return self._seq

    def subscribe(self, subscriber: SubscriberType) -> None:
        """Register a subscriber (Sink instance or async callback)."""
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: SubscriberType) -> None:
        """Unregister a subscriber."""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    async def publish(self, event: AgentEvent) -> AgentEvent:
        """
        Increments event sequence counter, assigns event.seq, stores event in ring buffer,
        and dispatches concurrently to all registered subscribers.
        """
        self._seq += 1
        event.seq = self._seq
        self.ring_buffer.append(event)

        if self._subscribers:
            tasks = []
            for sub in list(self._subscribers):
                if hasattr(sub, "consume") and callable(getattr(sub, "consume")):
                    tasks.append(self._safe_call(sub.consume, event))
                elif callable(sub):
                    tasks.append(self._safe_call(sub, event))

            if tasks:
                await asyncio.gather(*tasks)

        return event

    async def _safe_call(self, func: Callable[[AgentEvent], Awaitable[Any]], event: AgentEvent) -> None:
        try:
            res = func(event)
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
        except Exception as exc:
            logger.warning(f"Error in event subscriber {func}: {exc}", exc_info=True)

    def get_since(self, seq: int) -> list[AgentEvent]:
        """Return all historical events from ring buffer with seq > target seq."""
        return [evt for evt in self.ring_buffer if evt.seq > seq]
