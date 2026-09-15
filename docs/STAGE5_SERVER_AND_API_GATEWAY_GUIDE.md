# Stage 5 Server & API Gateway Guide

This document provides a complete technical guide to **Stage 5** of **AgentSentrix**: the FastAPI Application Lifespan Assembly, WebSocket `ConnectionManager` (with `since=<seq>` catchup streaming), REST API endpoints (`/health`, `/events`, `/graph`, `/decide`), `GraphProjection` engine, Static Dashboard mounting, and LLM/Environment configuration guide.

---

## 1. Executive Summary & Repository Status

- **Stage Status**: **Stage 5 (Server & API Gateway) is 100% complete and fully verified**.
- **Test Suite Pass Rate**: **26 out of 26 tests PASSED (100% success in 5.72s)** across Stage 1, Stage 2, Stage 3, Stage 4, and Stage 5.
- **REST Gateway**: FastAPI server assembled with lifespan context wiring all backend sinks, event bus, Redis cache, evaluators, and proxies.
- **WebSocket Gateway**: Real-time event streaming and catchup replay stream (`ws://...?since=<seq>`).
- **Static UI Host**: Dashboard static assets mounted from `core/agentsentrix/web/`.

---

## 2. LLM & Environment Variables Guide

Here is the exact breakdown of when LLMs and environment variables (`.env`) are required vs optional:

### A. Tier 0 (YAML Policy Rules & Shannon Entropy) — **NO LLM Needed**
- **Requirements**: Zero API keys or LLM services. Works 100% locally out-of-the-box.
- **Execution Speed**: $\sim 1\text{ms}$.
- **Function**: Matches pattern rules in `rules.yaml` (`.env`, `rm -rf`, `curl | sh`) and detects high-entropy secret keys ($>3.8$).

### B. Tier 1 (Local Ollama Classifier) — **LOCAL AI (No Cloud Keys)**
- **Requirements**: Local Ollama service running on `http://localhost:11434` with model `qwen2.5-coder:1.5b`.
- **API Key**: **None needed** (100% local inference).
- **Fallback Behavior**: If Ollama is offline/not installed, the system emits an explicit `UserWarning` and safely bypasses Tier 1 without process crashes.

### C. Tier 2 (Groq LLM-as-a-Judge) — **CLOUD LLM (GROQ_API_KEY)**
- **Requirements**: `GROQ_API_KEY` set in environment or `.env` file.
- **When it fires**: Only fires when an action score lands in the **ambiguous risk band (30 – 70)**.
- **Fallback Behavior**: If `GROQ_API_KEY` is missing or Groq API is unreachable, the system emits an explicit `UserWarning` and safely falls back to Tier 0 & Tier 1 scores without throwing exceptions.

---

## 3. Directory Hierarchy & Server Subsystem Files

```
agentsentrix/
├── pyproject.toml
├── requirements.txt
├── AGENTS.md
├── Makefile
├── STRUCTURE.md
│
├── core/agentsentrix/
│   ├── bus/                     # EventBus, StateCache (Redis), DuckDB & JSONL Sinks
│   ├── engine/                  # MultiTierEvaluator & BlastRadiusCalculator
│   ├── policy/                  # YAML Rules & PolicyLoader
│   ├── proxy/                   # MCPProxy & QuarantineManager
│   ├── sensors/                 # ReplaySensor & Shell Shim Interceptor
│   │
│   ├── projection/
│   │   └── graph_projection.py  # Event stream → GraphSnapshot topology projection
│   │
│   └── server/                  # Server & API Gateway Subsystem
│       ├── app.py               # FastAPI application assembly + Lifespan lifecycle wiring
│       ├── ws.py                # ConnectionManager (WebSocket streaming & since=<seq> catchup)
│       ├── routes.py            # REST endpoints (/health, /events, /graph, /decide) & WS route
│       └── static.py            # Static file server mounting Next.js UI build
│
├── docs/
│   ├── STAGE1_STATUS_AND_VERIFICATION.md
│   ├── STAGE2_RISK_ENGINE_AND_POLICY_GUIDE.md
│   ├── STAGE3_STATUS_AND_VERIFICATION.md
│   ├── STAGE4_SHELL_SHIM_AND_INTERCEPTOR_GUIDE.md
│   └── STAGE5_SERVER_AND_API_GATEWAY_GUIDE.md # (This document)
│
└── tests/
    ├── test_stage1.py           # Stage 1 persistence & bus tests (1 passed)
    ├── test_stage2.py           # Stage 2 risk engine & policy tests (7 passed)
    ├── test_stage3.py           # Stage 3 MCP proxy & transport tests (7 passed)
    ├── test_stage3_shim.py      # Stage 4 Shell shim interceptor tests (6 passed)
    └── test_stage5.py           # Stage 5 Server REST, WS & Graph tests (5 passed)
```

---

## 4. Subsystem Architecture & REST OpenAPI Specification

```
                               ┌─────────────────────────────────┐
                               │     FastAPI Server (app.py)     │
                               └────────────────┬────────────────┘
                                                │
           ┌────────────────────────────────────┼────────────────────────────────────┐
           ▼                                    ▼                                    ▼
┌──────────────────────┐             ┌──────────────────────┐             ┌──────────────────────┐
│ REST API (routes.py) │             │  WebSocket Gateway   │             │ Static UI Host       │
│                      │             │  (ws.py /ws)         │             │ (static.py /out)     │
└──────────┬───────────┘             └──────────┬───────────┘             └──────────────────────┘
           │                                    │
           ├─► GET  /health                     ├─► Real-Time Broadcast
           ├─► GET  /events (DuckDB)            └─► Reconnect Catchup (?since=seq)
           ├─► GET  /graph  (Projection)
           └─► POST /decide (Quarantine)
```

### 4.1 REST API Endpoint Specification

#### 1. `GET /health`
Verifies core service status (Redis, DuckDB, EventBus sequence).
- **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "redis_connected": true,
    "duckdb_event_count": 42,
    "bus_current_seq": 42
  }
  ```

#### 2. `GET /events`
Fetches paginated event history from DuckDB analytical storage.
- **Query Parameters**:
  - `limit`: int (default `50`, max `1000`)
  - `offset`: int (default `0`)
  - `session_id`: string (optional)
- **Response `200 OK`**:
  ```json
  {
    "events": [ { "id": "evt_001", "seq": 1, ... } ],
    "total_count": 42,
    "limit": 50,
    "offset": 0
  }
  ```

#### 3. `GET /graph`
Returns the current topology projection snapshot (`GraphSnapshot`).
- **Query Parameter**: `session_id` (default `"default_session"`)
- **Response `200 OK`**:
  ```json
  {
    "session_id": "default_session",
    "nodes": [
      { "id": "agent:agent_01", "kind": "agent", "label": "MCP Agent", "max_risk": 0, "event_count": 1 }
    ],
    "links": [
      { "id": "agent:agent_01->file:README.md", "source": "agent:agent_01", "target": "file:README.md", "max_risk": 0 }
    ],
    "seq": 42
  }
  ```

#### 4. `POST /decide`
Accepts operator decision (allowed or blocked) to resolve in-flight `QuarantineManager` futures and updates Redis state cache. Broadcasts decision updates to connected WebSockets.
- **Request Body**:
  ```json
  {
    "event_id": "evt_quarantined_123",
    "verdict": "allowed",
    "note": "Approved by security officer"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "success": true,
    "event_id": "evt_quarantined_123",
    "verdict": "allowed",
    "note": "Approved by security officer"
  }
  ```

#### 5. `WebSocket /ws`
Real-time telemetry streaming endpoint supporting client reconnection catchups.
- **Connection URL**: `ws://localhost:8000/ws` or `ws://localhost:8000/ws?since=10`
- **Wire Envelope Format**:
  ```json
  {
    "v": "1.0",
    "type": "event",
    "ts": "2026-09-15T17:00:00Z",
    "data": { "id": "evt_001", "seq": 11, ... }
  }
  ```

---

## 5. Verification & Testing Handbook

### 5.1 Verify Docker & Infrastructure
```powershell
# Check Redis container status
docker ps --filter "name=agentsentrix-redis"

# Verify Redis connectivity from Python
.venv\Scripts\python.exe -c "import redis; r = redis.Redis(host='localhost', port=6379); print('Redis Ping:', r.ping())"
```

### 5.2 Start Server via Uvicorn CLI
```powershell
.venv\Scripts\uvicorn.exe core.agentsentrix.server.app:app --host 0.0.0.0 --port 8000 --reload
```

### 5.3 Test REST Endpoints via Curl / HTTP
```powershell
# Health Endpoint
curl http://localhost:8000/health

# Events Endpoint
curl http://localhost:8000/events?limit=5

# Graph Topology Endpoint
curl http://localhost:8000/graph
```

### 5.4 Execute Full System Pytest Suite (All 26 Tests)
```powershell
.venv\Scripts\pytest.exe tests/test_stage1.py tests/test_stage2.py tests/test_stage3.py tests/test_stage3_shim.py tests/test_stage5.py -v
```

---

## 6. Full System Test Matrix (26 / 26 Passed)

```
tests/test_stage1.py::test_stage1_complete_flow PASSED                   [  3%]
tests/test_stage2.py::test_shannon_entropy PASSED                        [  7%]
tests/test_stage2.py::test_tier0_yaml_rules PASSED                       [ 11%]
tests/test_stage2.py::test_blast_radius_calculator PASSED                [ 15%]
tests/test_stage2.py::test_multitier_evaluator_full_flow PASSED          [ 19%]
tests/test_stage2.py::test_resilience_warning_emission PASSED            [ 23%]
tests/test_stage2.py::test_path_traversal_evasion_prevention PASSED      [ 26%]
tests/test_stage2.py::test_tier1_tier2_mock_responses PASSED             [ 30%]
tests/test_stage3.py::test_mock_mcp_servers PASSED                       [ 34%]
tests/test_stage3.py::test_proxy_allowed_flow PASSED                     [ 38%]
tests/test_stage3.py::test_proxy_blocked_flow PASSED                     [ 42%]
tests/test_stage3.py::test_proxy_quarantine_resolution_allowed PASSED    [ 46%]
tests/test_stage3.py::test_proxy_quarantine_resolution_rejected PASSED   [ 50%]
tests/test_stage3.py::test_jsonrpc_stdio_transport PASSED                [ 53%]
tests/test_stage3.py::test_quarantine_state_sync_with_redis PASSED       [ 57%]
tests/test_stage3_shim.py::test_shim_manager_installation PASSED         [ 61%]
tests/test_stage3_shim.py::test_shim_runner_find_real_binary PASSED      [ 65%]
tests/test_stage3_shim.py::test_shim_runner_allowed_flow PASSED          [ 69%]
tests/test_stage3_shim.py::test_shim_runner_blocked_flow PASSED          [ 73%]
tests/test_stage3_shim.py::test_shim_runner_quarantine_flow PASSED       [ 76%]
tests/test_stage3_shim.py::test_shim_stdin_passthrough PASSED            [ 80%]
tests/test_stage5.py::test_health_endpoint PASSED                        [ 84%]
tests/test_stage5.py::test_events_endpoint PASSED                        [ 88%]
tests/test_stage5.py::test_graph_endpoint PASSED                         [ 92%]
tests/test_stage5.py::test_decide_endpoint PASSED                        [ 96%]
tests/test_stage5.py::test_websocket_stream_and_catchup PASSED           [100%]

======================== 26 passed in 5.72s ========================
```
