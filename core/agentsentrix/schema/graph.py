# schema/graph.py
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field
from .enums import NodeKind, Verdict

class GraphNode(BaseModel):
    id: str                  # "agent:refactor-01" / "file:/repo/.env"
    kind: NodeKind
    label: str
    max_risk: int = 0
    event_count: int = 0
    last_seen: datetime
    meta: dict[str, Any] = {}

class GraphLink(BaseModel):
    id: str                  # f"{source}->{target}"
    source: str
    target: str
    last_verdict: Verdict
    max_risk: int = 0
    count: int = 0
    last_event_id: str
    last_ts: datetime

class GraphSnapshot(BaseModel):
    session_id: str
    nodes: list[GraphNode]
    links: list[GraphLink]
    seq: int                 # client resumes from here