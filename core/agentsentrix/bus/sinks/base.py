from typing import Protocol, runtime_checkable
from ...schema.events import AgentEvent

@runtime_checkable
class Sink(Protocol):
    """Protocol for event sinks in AgentSentrix."""
    async def consume(self, event: AgentEvent) -> None:
        """Process or persist an incoming AgentEvent asynchronously."""
        ...
