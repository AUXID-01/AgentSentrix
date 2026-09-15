# schema/events.py
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from .enums import *

def _now() -> datetime:
    return datetime.now(timezone.utc)

class AgentRef(BaseModel):
    id: str                        # "refactor-01"
    name: str                      # "Refactor Agent"
    model: str | None = None       # "qwen2.5-coder:7b"
    framework: str | None = None   # "langgraph"
    task: str | None = None        # assigned task, for intent-drift in Phase 3

class Target(BaseModel):
    kind: NodeKind
    label: str                     # ".env"
    path: str | None = None        # "/repo/.env"
    host: str | None = None        # "api.attacker.dev"

    @property
    def node_id(self) -> str:
        return f"{self.kind.value}:{self.path or self.host or self.label}"

class TierScores(BaseModel):
    t0_rules: int | None = None
    t1_local: int | None = None
    t2_llm: int | None = None

class RiskAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: Verdict
    tier_scores: TierScores = TierScores()
    policy_ids: list[str] = []
    rationale: str = ""
    engine: str = "stub"
    cached: bool = False

class BlastRadius(BaseModel):
    files_touched: int = 0
    reversible: bool = True
    secrets_exposed: bool = False
    egress: bool = False
    score: int = Field(default=0, ge=0, le=100)

class AgentEvent(BaseModel):
    schema_version: SchemaVersion = SchemaVersion.V1
    id: str                         # "evt_01h..."
    seq: int = 0                    # assigned by bus, monotonic
    ts: datetime = Field(default_factory=_now)
    session_id: str
    sensor: Sensor
    agent: AgentRef
    action_type: ActionType
    target: Target
    raw_payload: str                # the literal command / tool args
    task_context: str | None = None
    risk: RiskAssessment
    blast_radius: BlastRadius = BlastRadius()
    latency_ms: float = 0.0
    decision_ts: datetime | None = None
    parent_id: str | None = None    # call-stack chain for drilldown

class DecisionUpdate(BaseModel):
    event_id: str
    verdict: Verdict
    decided_by: str = "human"
    decided_at: datetime = Field(default_factory=_now)
    note: str | None = None