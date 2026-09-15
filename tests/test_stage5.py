import os
import json
import asyncio
import pytest
from fastapi.testclient import TestClient

from core.agentsentrix.server.app import create_app
from core.agentsentrix.schema.enums import Sensor, ActionType, NodeKind, Verdict
from core.agentsentrix.schema.events import AgentEvent, AgentRef, Target, RiskAssessment

def make_test_event(idx: int) -> AgentEvent:
    score = min(10 * idx, 100)
    return AgentEvent(
        id=f"evt_s5_{idx:03d}",
        session_id="session_stage5",
        sensor=Sensor.MCP_PROXY,
        agent=AgentRef(id="agent_s5", name="Stage5 Agent"),
        action_type=ActionType.FILE_READ,
        target=Target(kind=NodeKind.FILE, label=f"test_{idx}.txt", path=f"/tmp/test_{idx}.txt"),
        raw_payload=f"cat /tmp/test_{idx}.txt",
        risk=RiskAssessment(score=score, verdict=Verdict.ALLOWED)
    )

@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "redis_connected" in data
    assert "duckdb_event_count" in data
    assert "bus_current_seq" in data

@pytest.mark.asyncio
async def test_events_endpoint(client: TestClient):
    bus = client.app.state.bus
    for i in range(1, 6):
        event = make_test_event(i)
        await bus.publish(event)

    response = client.get("/events?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert data["total_count"] >= 5

@pytest.mark.asyncio
async def test_graph_endpoint(client: TestClient):
    bus = client.app.state.bus
    event = make_test_event(1)
    await bus.publish(event)

    response = client.get("/graph?session_id=session_stage5")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) >= 2  # Agent node + Target node
    assert len(data["links"]) >= 1

@pytest.mark.asyncio
async def test_decide_endpoint(client: TestClient):
    quarantine_mgr = client.app.state.quarantine_mgr
    event_id = "evt_decide_test_100"

    # Create pending quarantine future on running test loop
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    quarantine_mgr.pending_futures[event_id] = fut

    payload = {
        "event_id": event_id,
        "verdict": "allowed",
        "note": "Approved by security officer"
    }
    response = client.post("/decide", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["verdict"] == "allowed"
    assert fut.done()

def test_websocket_stream_and_catchup(client: TestClient):
    bus = client.app.state.bus

    # 1. Test live WebSocket streaming
    with client.websocket_connect("/ws") as websocket:
        # Receive initial HELLO envelope
        hello_data = websocket.receive_json()
        assert hello_data["type"] == "hello"

        # Publish an event to the bus via event loop or sync subscriber trigger
        event = make_test_event(9)
        bus._seq += 1
        event.seq = bus._seq
        bus.ring_buffer.append(event)
        
        ws_manager = client.app.state.ws_manager
        client.portal.call(ws_manager.on_event, event)

        # Receive streamed EVENT envelope
        evt_data = websocket.receive_json()
        assert evt_data["type"] == "event"
        assert evt_data["data"]["id"] == "evt_s5_009"

    # 2. Test WebSocket catchup stream with ?since=<seq>
    with client.websocket_connect("/ws?since=0") as websocket_catchup:
        hello_data = websocket_catchup.receive_json()
        assert hello_data["type"] == "hello"

        # Should receive historical events
        catchup_data = websocket_catchup.receive_json()
        assert catchup_data["type"] == "event"
        assert "id" in catchup_data["data"]
