from abc import ABC, abstractmethod
from typing import Optional
from ..schema.events import AgentEvent
from ..bus.bus import EventBus

class Sensor(ABC):
    """Abstract Base Class for AgentSentrix Telemetry Sensors."""

    def __init__(self, bus: Optional[EventBus] = None) -> None:
        self.bus = bus

    @abstractmethod
    async def start(self) -> None:
        """Start the sensor ingestion stream."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the sensor ingestion stream."""
        pass

    async def emit_event(self, event: AgentEvent) -> AgentEvent:
        """Publish an AgentEvent to the registered EventBus."""
        if self.bus:
            return await self.bus.publish(event)
        return event
