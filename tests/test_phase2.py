import pytest
import asyncio
import tempfile
import os
import duckdb
from core.agentsentrix.bus.sinks.duckdb_sink import DuckDBSink
from core.agentsentrix.schema.events import AgentEvent, AgentRef, Target, RiskAssessment
from core.agentsentrix.schema.enums import Sensor, ActionType, NodeKind, Verdict
from core.agentsentrix.engine.evaluator import MultiTierEvaluator

@pytest.mark.asyncio
async def test_duckdb_concurrent_writes():
    """Phase 2 Test A: 50 concurrent writes using asyncio.gather without lock contention or data loss."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_concurrent.duckdb")
        sink = DuckDBSink(db_path=db_path)

        async def publish_event(idx: int):
            event = AgentEvent(
                id=f"evt_phase2_{idx:03d}",
                seq=idx,
                session_id="session_test_phase2",
                sensor=Sensor.MCP_PROXY,
                agent=AgentRef(id=f"agent-{idx}", name=f"Agent-{idx}", task="Concurrent write test"),
                action_type=ActionType.FILE_READ,
                target=Target(kind=NodeKind.FILE, label="test_file", path=f"/tmp/test_{idx}.txt"),
                raw_payload=f"Payload data {idx}",
                risk=RiskAssessment(score=10, verdict=Verdict.ALLOWED)
            )
            await sink.consume(event)

        # Publish 50 events concurrently
        tasks = [publish_event(i) for i in range(50)]
        await asyncio.gather(*tasks)

        # Query DuckDB to verify row count
        conn = duckdb.connect(sink.db_path)
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        conn.close()
        sink.close()

        assert count == 50, f"Expected 50 persistent events, found {count}"

@pytest.mark.asyncio
async def test_evaluator_degraded_tier1_offline():
    """Phase 2 Test B: Evaluator handles offline Ollama gracefully with explicit degradation indicators."""
    # Point evaluator to non-existent Ollama port
    evaluator = MultiTierEvaluator(ollama_url="http://127.0.0.1:59999")

    event = AgentEvent(
        id="evt_degraded_001",
        seq=1,
        session_id="session_degraded_test",
        sensor=Sensor.SHELL_SHIM,
        agent=AgentRef(id="agent-007", name="TestAgent", task="Test offline Ollama handling"),
        action_type=ActionType.FILE_WRITE,
        target=Target(kind=NodeKind.FILE, label="sensitive_file", path="/etc/config"),
        raw_payload="write sensitive data",
        risk=RiskAssessment(score=0, verdict=Verdict.ALLOWED)
    )

    assessment, blast_radius = await evaluator.assess(event)

    assert assessment.tier_scores.t1_local is None, "t1_local score should be None when Ollama is offline"
    assert "tier_1_offline" in assessment.degraded_tiers, "degraded_tiers should contain 'tier_1_offline'"
    assert "[Tier 1 Local SLM Offline — Policy Fallback Active]" in assessment.rationale
    assert assessment.verdict is not None, "Evaluation must produce a valid verdict despite Tier 1 offline"
