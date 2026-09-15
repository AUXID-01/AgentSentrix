# schema/ws.py
class WsType(str, Enum):
    HELLO = "hello"
    SNAPSHOT = "snapshot"
    EVENT = "event"
    DECISION = "decision_update"
    STATS = "stats"
    ERROR = "error"

class WsEnvelope(BaseModel):
    v: str = "1.0"
    type: WsType
    ts: datetime = Field(default_factory=_now)
    data: dict[str, Any]