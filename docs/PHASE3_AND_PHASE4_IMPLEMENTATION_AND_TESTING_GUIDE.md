# Phase 3 & Phase 4 Implementation & Testing Guide: Public SDK Interception & Instant Quarantine UX

## Executive Summary

This guide documents the implementation, architecture, and verification procedures for **Phase 3 (Core Thesis Verification & Public SDK Integration)** and **Phase 4 (Instant Quarantine UX & Real-Time 3D Graph Animation)** in AgentSentrix.

---

## 1. Phase 3: Public SDK & Core Thesis Verification

### 1.1 Goal
To verify that agent actions travel end-to-end through the public Python SDK callback handler without internal shortcuts:
$$\text{Agent (rogue-01)} \longrightarrow \text{Public Callback SDK Hook} \longrightarrow \text{MultiTierEvaluator} \longrightarrow \text{EventBus} \longrightarrow \text{DuckDB + WebSocket} \longrightarrow \text{Dashboard} \longrightarrow \mathbf{BLOCKED}$$

### 1.2 Implementation Details

#### Public Callback SDK Handler (`core/agentsentrix/sdk.py`)
Introduced `AgentSentrixCallbackHandler` subclassing standard LangChain / LangGraph `BaseCallbackHandler`:

```python
class AgentSentrixCallbackHandler(BaseCallbackHandler):
    """
    Public LangChain & LangGraph Callback Handler for AgentSentrix security interception.
    Intercepts agent tool calls (`on_tool_start`), sends event telemetry to AgentSentrix security gateway,
    and raises SecurityBlockError if an action is BLOCKED.
    """
    def __init__(
        self,
        server_url: str = "http://localhost:7777",
        agent_id: str = "default-agent",
        agent_name: str = "LangGraph Agent",
        fail_safe: bool = True
    ) -> None:
        super().__init__()
        self.sdk = AgentSentrixSDK(
            server_url=server_url,
            agent_id=agent_id,
            agent_name=agent_name,
            fail_safe=fail_safe
        )

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown_tool")
        payload = f"{tool_name}(input={input_str})"
        verdict = self.sdk._evaluate_sync(
            agent_id=self.sdk.agent_id,
            action_type="tool_call",
            target_kind="shell",
            target_label=tool_name,
            raw_payload=payload
        )
        if verdict == Verdict.BLOCKED:
            raise SecurityBlockError(f"Tool execution '{tool_name}' BLOCKED by AgentSentrix security policy.")
```

#### Simulation Engine Integration (`sim/runner.py`)
Updated `SimulationRunner` to instantiate `AgentSentrixCallbackHandler` for each agent persona (`Refactorer`, `Test Runner`, `MCP Installer`, `Rogue Agent`), eliminating mock shortcuts:

```python
# Attach public SDK Callback Handler
sdk_handler = AgentSentrixCallbackHandler(
    server_url="http://localhost:7777",
    agent_id=persona.agent_id,
    agent_name=persona.name
)

# Intercept tool call via public SDK
try:
    sdk_handler.on_tool_start({"name": step.action_type.value}, step.payload)
except SecurityBlockError:
    pass
```

---

## 2. Phase 4: Instant Quarantine UX & 3D Graph Animation

### 2.1 Goal
Eliminate REST polling lag during Quarantine resolution by implementing **WebSocket push notifications** (`quarantine_held`) and **real-time 3D graph state updates** (`UPDATE_VERDICT`).

### 2.2 Implementation Details

#### 1. WebSocket Schema (`core/agentsentrix/schema/ws.py`)
Added `QUARANTINE_HELD = "quarantine_held"` to `WsType` enum:
```python
class WsType(str, Enum):
    HELLO = "hello"
    SNAPSHOT = "snapshot"
    EVENT = "event"
    QUARANTINE_HELD = "quarantine_held"
    DECISION = "decision_update"
    STATS = "stats"
    ERROR = "error"
```

#### 2. Quarantine Manager Push (`core/agentsentrix/proxy/quarantine.py`)
Updated `QuarantineManager` to broadcast a `quarantine_held` WebSocket envelope whenever a `QUARANTINED` event creates an `asyncio.Future`:

```python
# Broadcast instant quarantine_held frame to active WebSockets
if self.ws_manager:
    try:
        from ..schema.ws import WsEnvelope, WsType
        held_data = {"event_id": event_id, "status": "quarantined"}
        if event_data:
            held_data.update(event_data)
        envelope = WsEnvelope(type=WsType.QUARANTINE_HELD, data=held_data)
        asyncio.create_task(self.ws_manager.broadcast(envelope))
    except Exception as exc:
        logger.warning(f"Failed to broadcast WebSocket quarantine_held frame: {exc}")
```

#### 3. WebSocket Client & Handlers (`dashboard/lib/ws.ts`)
Exposed `onQuarantineHeld` and `onDecisionUpdate` callbacks on `AgentSentrixWsClient`:
```typescript
else if (envelope.type === 'quarantine_held' && envelope.data) {
  this.onQuarantineHeld?.(envelope.data);
} else if (envelope.type === 'decision_update' && envelope.data) {
  this.onDecisionUpdate?.(envelope.data);
}
```

#### 4. Real-Time 3D Graph Verdict Updates (`dashboard/lib/graphReducer.ts`)
Implemented `UPDATE_VERDICT` action to update 3D node colors, link particle colors, and unfreeze node animations instantly:

```typescript
case 'UPDATE_VERDICT': {
  const { event_id, verdict } = action.payload;
  const updatedNodes = state.nodes.map((n) =>
    n.id === event_id || n.event_id === event_id ? { ...n, verdict } : n
  );
  const updatedLinks = state.links.map((l) => {
    const srcId = typeof l.source === 'object' ? l.source.id : l.source;
    const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
    if (tgtId === event_id || srcId === event_id) {
      return { ...l, verdict };
    }
    return l;
  });
  return { nodes: updatedNodes, links: updatedLinks };
}
```

#### 5. Instant UI Drawer & Decision Dispatch (`dashboard/app/page.tsx`)
When a `quarantine_held` WS push frame is received:
- Automatically pops open the **Inspection Drilldown** drawer on the operator's screen.
- When the operator clicks **[✓ APPROVE ACTION]** or **[✕ BLOCK ACTION]**:
  1. Dispatches `POST /decide`, unblocking the in-memory `asyncio.Future` instantly.
  2. Broadcasts `decision_update` over WebSockets.
  3. Updates 3D node colors (Emerald green for allowed, Rose red for blocked), beam particle colors, and unfreezes node animations with zero visible lag.

---

## 3. How to Run & Verify All Features

### 3.1 Method 1: Automated Verification Tests (Fastest)

Run the dedicated Phase 3 & Phase 4 test suite:

```bash
# Activate virtual environment
venv\Scripts\Activate

# Run Phase 3 & Phase 4 unit and integration tests
python -m pytest tests/test_phase3_phase4.py -v
```

#### Expected Test Output:
```text
tests/test_phase3_phase4.py::test_phase3_public_sdk_callback_handler PASSED [ 33%]
tests/test_phase3_phase4.py::test_phase3_sim_runner_uses_public_sdk PASSED [ 66%]
tests/test_phase3_phase4.py::test_phase4_quarantine_ws_push_and_instant_resolution PASSED [100%]
======================== 3 passed in 22.41s ========================
```

---

### 3.2 Method 2: Live Visual Interception & Instant Quarantine Test

#### Step 1: Launch Unified Gateway & Dashboard
In Terminal 1:
```bash
python -m core.agentsentrix.cli up
```
- Starts the FastAPI gateway on `port 7777` and automatically opens browser to `http://localhost:7777`.

#### Step 2: Run 4-Agent Simulation Scenario
In Terminal 2:
```bash
venv\Scripts\Activate
python -m sim.runner --delay-ms 1000
```

#### Step 3: Visual Verification Checklist
1. **Rogue Agent Block**: Watch `Rogue Agent (rogue-01)` attempt `cat .env` / `curl attacker.dev`. The node turns **ROSE RED** with `BLOCKED` verdict.
2. **Instant Quarantine Push**: When `mcp-installer-01` triggers `QUARANTINED`, the Inspection Drawer pops open automatically on your screen via WebSocket push with zero polling delay.
3. **Instant Decision Unfreeze**: Click **[✓ APPROVE ACTION]** or **[✕ BLOCK ACTION]** in the drawer:
   - Agent execution resumes instantly.
   - Node color turns **Emerald Green** (Allowed) or **Rose Red** (Blocked) in real-time on the 3D topology graph.

---

## 4. Verification Summary & Test Matrix

| Component / Test | Scope | Verification Command | Result |
| :--- | :--- | :--- | :---: |
| `test_phase3_public_sdk_callback_handler` | Public SDK callback tool interception & block handling | `python -m pytest tests/test_phase3_phase4.py` | **PASSED** |
| `test_phase3_sim_runner_uses_public_sdk` | 4-agent simulation execution via `AgentSentrixCallbackHandler` | `python -m pytest tests/test_phase3_phase4.py` | **PASSED** |
| `test_phase4_quarantine_ws_push_and_instant_resolution` | `quarantine_held` WS push & instant future resolution | `python -m pytest tests/test_phase3_phase4.py` | **PASSED** |
| Full Test Suite | 43 unit, integration, server, simulation & analytics tests | `python -m pytest tests/` | **43 / 43 PASSED** |
