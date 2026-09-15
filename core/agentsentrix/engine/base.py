from abc import ABC, abstractmethod
from ..schema.events import AgentEvent, RiskAssessment, BlastRadius

class RiskEngine(ABC):
    """Abstract Base Class / Protocol for AgentSentrix Risk Engines."""

    @abstractmethod
    async def assess(self, event: AgentEvent) -> tuple[RiskAssessment, BlastRadius]:
        """Assess an incoming AgentEvent and return (RiskAssessment, BlastRadius)."""
        pass
