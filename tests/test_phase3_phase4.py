import pytest
import asyncio
from core.agentsentrix.sdk import AgentSentrixCallbackHandler, AgentSentrixSDK, SecurityBlockError
from core.agentsentrix.schema.enums import Verdict, Sensor, ActionType, NodeKind
from core.agentsentrix.schema.events import AgentEvent, AgentRef, Target, RiskAssessment
from core.agentsentrix.proxy.quarantine import QuarantineManager
from core.agentsentrix.schema.ws import WsType, WsEnvelope
from sim.runner import SimulationRunner

class MockWsManager:
    def __init__(self):
        self.broadcasted_envelopes: list[WsEnvelope] = []

    async def broadcast(self, envelope: WsEnvelope) -> None:
        self.broadcasted_envelopes.append(envelope)

@pytest.mark.asyncio
async def test_phase3_public_sdk_callback_handler():
    """Phase 3 Test: Verify AgentSentrixCallbackHandler public SDK callback execution."""
    handler = AgentSentrixCallbackHandler(
        server_url="http://127.0.0.1:59999", # Unreachable server triggers fail-safe
        agent_id="test-agent-001",
        agent_name="Test Public SDK Agent",
        fail_safe=True
    )
    
    assert handler.sdk.agent_id == "test-agent-001"
    
    # Executing safe tool call using public SDK callback
    handler.on_tool_start({"name": "file_read"}, "src/main.py")

@pytest.mark.asyncio
async def test_phase3_sim_runner_uses_public_sdk():
    """Phase 3 Test: Execute 4-agent scenario with SimulationRunner using public SDK handler."""
    runner = SimulationRunner()
    result = await runner.run_scenario(auto_resolve_quarantine=True, step_delay_ms=0.0)

    assert result.total_agents == 4
    assert result.total_events == 8
    assert result.blocked_count >= 1, "Rogue Agent must produce at least 1 BLOCKED event"

@pytest.mark.asyncio
async def test_phase4_quarantine_ws_push_and_instant_resolution():
    """Phase 4 Test: Verify QuarantineManager pushes WS quarantine_held frame and resolves in-memory future immediately."""
    ws_mgr = MockWsManager()
    q_mgr = QuarantineManager(ws_manager=ws_mgr)

    event_id = "evt_quarantine_ws_test"
    future = q_mgr.create_quarantine_future(event_id, {"agent": "mcp-installer-01", "tool": "install_pkg"})

    # Give event loop a micro-tick to let broadcast task run
    await asyncio.sleep(0.01)

    # 1. Verify WebSocket push notification frame was broadcasted immediately
    assert len(ws_mgr.broadcasted_envelopes) == 1
    pushed_envelope = ws_mgr.broadcasted_envelopes[0]
    assert pushed_envelope.type == WsType.QUARANTINE_HELD
    assert pushed_envelope.data["event_id"] == event_id
    assert not future.done()

    # 2. Operator approves action via resolve_quarantine
    resolved = q_mgr.resolve_quarantine(event_id, Verdict.ALLOWED, note="Instant WS approval test")
    assert resolved is True
    assert future.done()
    res = future.result()
    assert res["verdict"] == Verdict.ALLOWED
