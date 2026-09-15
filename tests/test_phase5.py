import pytest
import asyncio
import os
import json
from core.agentsentrix.sensors.replay import ReplaySensor
from core.agentsentrix.bus.bus import EventBus
from core.agentsentrix.schema.events import AgentEvent
from core.agentsentrix.server.app import create_app

SEED_FILE = "data/seed/demo_session.jsonl"

def test_phase5_seed_file_integrity():
    """Phase 5 Test: Verify data/seed/demo_session.jsonl contains 8 valid serialized AgentEvent objects."""
    assert os.path.exists(SEED_FILE), f"Seed trace file missing: {SEED_FILE}"
    
    events = []
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(AgentEvent.model_validate_json(line))

    assert len(events) == 8, f"Expected 8 seed events, found {len(events)}"
    
    # Verify Rogue Agent blocked events exist in trace
    blocked_events = [e for e in events if e.risk.verdict == "blocked" or e.risk.verdict.value == "blocked"]
    assert len(blocked_events) >= 1, "Seed trace must contain blocked rogue agent events"

@pytest.mark.asyncio
async def test_phase5_replay_sensor_emission():
    """Phase 5 Test: Verify ReplaySensor reads seed trace and emits all events onto EventBus."""
    bus = EventBus()
    received_events: list[AgentEvent] = []

    async def on_event(evt: AgentEvent):
        received_events.append(evt)

    bus.subscribe(on_event)

    # Replay trace at 100x speed for fast test execution
    sensor = ReplaySensor(jsonl_path=SEED_FILE, bus=bus, speed_factor=100.0)
    await sensor.start()

    # Allow asyncio loop to process events
    await asyncio.sleep(0.5)
    await sensor.stop()

    assert len(received_events) == 8, f"Expected 8 replayed events on bus, received {len(received_events)}"
    assert received_events[0].agent.id == "refactorer-01"
    assert received_events[-1].agent.id == "rogue-01"

def test_phase5_app_replay_factory():
    """Phase 5 Test: Verify FastAPI app factory initializes with replay_file mode cleanly."""
    app_inst = create_app(replay_file=SEED_FILE, speed=2.0)
    assert app_inst is not None
    assert app_inst.title == "AgentSentrix API Gateway & Real-Time Security Engine"
