import os
import shutil
import pytest
import duckdb

from core.agentsentrix.schema.enums import Sensor, ActionType, NodeKind, Verdict
from core.agentsentrix.schema.events import AgentEvent, AgentRef, Target, RiskAssessment, BlastRadius
from core.agentsentrix.bus.bus import EventBus
from core.agentsentrix.bus.sinks.duckdb_sink import DuckDBSink
from core.agentsentrix.bus.sinks.jsonl_sink import JSONLSink
from core.agentsentrix.bus.cache import StateCache

TEST_DB_PATH = "data/test_agentsentrix.duckdb"
TEST_JSONL_DIR = "data/test_sessions"
TEST_SESSION_ID = "test_session_001"
TEST_JSONL_FILE = f"{TEST_JSONL_DIR}/{TEST_SESSION_ID}.jsonl"

def make_mock_event(idx: int) -> AgentEvent:
    return AgentEvent(
        id=f"evt_{idx:03d}",
        session_id=TEST_SESSION_ID,
        sensor=Sensor.MCP_PROXY,
        agent=AgentRef(id="test_agent_1", name="Test Agent"),
        action_type=ActionType.FILE_READ,
        target=Target(kind=NodeKind.FILE, label="test.txt", path="/tmp/test.txt"),
        raw_payload=f"read_file(/tmp/test_{idx}.txt)",
        risk=RiskAssessment(score=10 * idx, verdict=Verdict.ALLOWED)
    )

@pytest.fixture(autouse=True)
def cleanup():
    # Setup clean directories
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    if os.path.exists(TEST_JSONL_DIR):
        try:
            shutil.rmtree(TEST_JSONL_DIR)
        except Exception:
            pass
    yield
    # Teardown
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    if os.path.exists(TEST_JSONL_DIR):
        try:
            shutil.rmtree(TEST_JSONL_DIR)
        except Exception:
            pass

@pytest.mark.asyncio
async def test_stage1_complete_flow():
    # Initialize components
    bus = EventBus(maxlen=1000)
    duckdb_sink = DuckDBSink(db_path=TEST_DB_PATH)
    jsonl_sink = JSONLSink(target_dir=TEST_JSONL_DIR)

    received_events: list[AgentEvent] = []

    async def custom_subscriber(event: AgentEvent):
        received_events.append(event)

    bus.subscribe(duckdb_sink)
    bus.subscribe(jsonl_sink)
    bus.subscribe(custom_subscriber)

    # -------------------------------------------------------------
    # 1. Bus Delivery: Publish 10 mock AgentEvent objects
    # -------------------------------------------------------------
    published_events: list[AgentEvent] = []
    for i in range(1, 11):
        event = make_mock_event(i)
        pub_event = await bus.publish(event)
        published_events.append(pub_event)

    assert len(received_events) == 10, f"Expected 10 events, got {len(received_events)}"
    for idx, evt in enumerate(received_events, start=1):
        assert evt.seq == idx, f"Expected sequence number {idx}, got {evt.seq}"

    # -------------------------------------------------------------
    # 2. DuckDB Integrity: Run query on DuckDB
    # -------------------------------------------------------------
    duckdb_sink.close()  # flush/close before querying directly
    con = duckdb.connect(TEST_DB_PATH)
    count = con.execute("SELECT count(*) FROM events").fetchone()[0]
    con.close()
    assert count == 10, f"Expected 10 events in DuckDB, got {count}"

    # -------------------------------------------------------------
    # 3. JSONL Integrity: Read .jsonl file line-by-line
    # -------------------------------------------------------------
    assert os.path.exists(TEST_JSONL_FILE), f"JSONL file missing at {TEST_JSONL_FILE}"
    with open(TEST_JSONL_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 10, f"Expected 10 lines in JSONL file, got {len(lines)}"

    deserialized_events: list[AgentEvent] = []
    for line in lines:
        parsed_event = AgentEvent.model_validate_json(line)
        deserialized_events.append(parsed_event)

    assert len(deserialized_events) == 10
    for original, deserialized in zip(published_events, deserialized_events):
        assert original.id == deserialized.id
        assert original.seq == deserialized.seq
        assert original.session_id == deserialized.session_id
        assert original.risk.score == deserialized.risk.score

    # -------------------------------------------------------------
    # 4. Ring Buffer Catchup: Call bus.get_since(seq=5)
    # -------------------------------------------------------------
    catchup_events = bus.get_since(seq=5)
    assert len(catchup_events) == 5, f"Expected 5 events, got {len(catchup_events)}"
    expected_seqs = [6, 7, 8, 9, 10]
    actual_seqs = [e.seq for e in catchup_events]
    assert actual_seqs == expected_seqs, f"Expected seqs {expected_seqs}, got {actual_seqs}"

    # -------------------------------------------------------------
    # 5. Cache Operations: Redis & State Cache Operations
    # -------------------------------------------------------------
    cache = StateCache(host="localhost", port=6379)
    assert cache.is_redis_connected() is True, "Redis container should be connected"

    dummy_hash = "sha256_action_payload_123"
    dummy_risk = RiskAssessment(score=85, verdict=Verdict.QUARANTINED, rationale="High risk shell exec")

    cache.set_verdict(dummy_hash, dummy_risk, ttl=3600)
    cached_verdict = cache.get_verdict(dummy_hash)

    assert cached_verdict is not None, "Verdict hit failed"
    assert cached_verdict.score == 85
    assert cached_verdict.verdict == Verdict.QUARANTINED
    assert cached_verdict.rationale == "High risk shell exec"

    # Test Quarantine Pending Store
    event_id = "evt_999"
    quarantine_payload = {"status": "quarantined", "future_key": "human_approval_key_1"}
    cache.set_quarantine(event_id, quarantine_payload, ttl=3600)
    retrieved_quarantine = cache.get_quarantine(event_id)

    assert retrieved_quarantine is not None
    assert retrieved_quarantine["status"] == "quarantined"
    assert retrieved_quarantine["future_key"] == "human_approval_key_1"
