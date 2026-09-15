# Phase 5 Guide: Record & Replay (Airplane-Mode Offline Fallback Trace)

## Executive Summary

Phase 5 introduces an immutable, offline-ready fallback trace mechanism for AgentSentrix. If local LLMs (Ollama), cloud judges (Groq), Docker sandboxes, or venue Wi-Fi fail, `agentsentrix replay` streams a real recorded session trace through the WebSocket event bus at identical timing — making it 100% indistinguishable from a live run on the 3D command dashboard.

---

## 1. Architecture & Design

### 1.1 Core Goals
1. **Trace Capture (`agentsentrix record`)**: Capture a full live 4-agent run into `data/seed/demo_session.jsonl` serialized with valid JSON schemas, `parent_id` lineage chains, risk scores, blast radius metrics, and verdicts (`ALLOWED`, `QUARANTINED`, `BLOCKED`).
2. **Offline Replay Sensor (`ReplaySensor`)**: Re-publish each event to `EventBus` while preserving original relative timestamp delays (divided by speed multiplier `x1.5`, `x2.0`), capping long pauses at 2.0s.
3. **Airplane Mode Indistinguishability**: The Next.js 3D dashboard renders replayed events through the exact same WebSocket stream, DuckDB storage, and WebGL rendering pipeline as live runs without making any network or API calls.

---

## 2. CLI Commands & Usage

### 2.1 Recording a Session (`agentsentrix record`)
Captures all 8 simulation telemetry events into an offline-ready trace file:

```bash
# Record live 4-agent scenario into data/seed/demo_session.jsonl
python -m core.agentsentrix.cli record --output data/seed/demo_session.jsonl --delay-ms 800
```

#### Output Trace (`data/seed/demo_session.jsonl`):
Contains 8 serialized JSON events representing:
- `Refactorer Agent`: Safe file read (`ALLOWED`) + High-entropy secret file write (`BLOCKED`).
- `Test Runner Agent`: Unit test shell execution (`ALLOWED`).
- `MCP Installer Agent`: Dangerous force git push (`QUARANTINED`).
- `Rogue Agent`: Safe README read (`ALLOWED`) + Credential/env file access (`BLOCKED`) + Exfiltration egress (`BLOCKED`).

---

### 2.2 Replaying a Session Offline (`agentsentrix replay`)
Launches the single-process security gateway and dashboard with `ReplaySensor` active:

```bash
# Replay session trace at 1.5x speed
python -m core.agentsentrix.cli replay data/seed/demo_session.jsonl --speed 1.5
```

- Automatically opens your browser to **`http://localhost:7777`**.
- Operates 100% offline with zero Wi-Fi, zero Ollama, and zero external API dependencies.

---

## 3. Step-by-Step Verification Procedure

### 3.1 Step A: Run Automated Unit & Integration Tests
Execute the Phase 5 test suite:

```bash
# Activate virtual environment
venv\Scripts\Activate

# Run Phase 5 tests
python -m pytest tests/test_phase5.py -v
```

#### Expected Output:
```text
tests/test_phase5.py::test_phase5_seed_file_integrity PASSED             [ 33%]
tests/test_phase5.py::test_phase5_replay_sensor_emission PASSED          [ 66%]
tests/test_phase5.py::test_phase5_app_replay_factory PASSED              [100%]
============================== 3 passed in 0.88s ==============================
```

---

### 3.2 Step B: The Airplane-Mode Check (Manual Demo Verification)

1. **Disconnect Wi-Fi / Disable Internet**.
2. **Stop Ollama** (`ollama stop` or close process).
3. Run the replay CLI command:
   ```bash
   python -m core.agentsentrix.cli replay data/seed/demo_session.jsonl --speed 1.5
   ```
4. **Observe the Dashboard (`http://localhost:7777`)**:
   - The 3D topology canvas animates, particle beams pulse, and the rogue agent triggers `BLOCKED` states in red.
   - Zero network connection errors or unhandled API exceptions occur.
   - The user cannot tell the difference between a live simulation and the replayed trace!

---

## 4. Verification Summary & Test Matrix

| Component / Test | Scope | Verification Command | Result |
| :--- | :--- | :--- | :---: |
| `test_phase5_seed_file_integrity` | Verified `data/seed/demo_session.jsonl` contains 8 valid serialized events | `python -m pytest tests/test_phase5.py` | **PASSED** |
| `test_phase5_replay_sensor_emission` | ReplaySensor reads trace file and emits events onto `EventBus` | `python -m pytest tests/test_phase5.py` | **PASSED** |
| `test_phase5_app_replay_factory` | Server factory initializes in offline replay mode cleanly | `python -m pytest tests/test_phase5.py` | **PASSED** |
| Full Test Suite | 46 unit, integration, server, simulation & analytics tests | `python -m pytest tests/` | **46 / 46 PASSED** |
