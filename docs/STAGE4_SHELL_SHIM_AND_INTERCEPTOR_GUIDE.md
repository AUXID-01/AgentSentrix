# AgentSentrix - Stage 4 Shell PATH Shim Interceptor & Telemetry Guide

This document provides a complete technical specification, architecture overview, developer usage guide, and verification handbook for the **Shell PATH Shim Interceptor Layer** of **AgentSentrix** (`core/agentsentrix/sensors/shim/`).

---

## 1. Executive Summary & System Status

- **System Status**: **Shell PATH Shim Interceptor Layer is 100% complete, edge-case hardened, and verified**.
- **Test Suite Pass Rate**: **21 out of 21 tests PASSED (100% success in 3.53s)** across Stage 1, Stage 2, Stage 3 MCP Proxy, and Shell Shim Interceptor.
- **Cross-Platform Support**: Generates executable POSIX `#!/bin/sh` scripts for Linux/macOS and Windows `.cmd` / `.bat` batch wrappers.
- **Docker & Cache Infrastructure**: Fully synchronized with containerized Redis instance (`agentsentrix-redis`) running on port `6379`.

---

## 2. Directory Hierarchy & Subsystem Files

```
agentsentrix/
├── pyproject.toml
├── requirements.txt
├── AGENTS.md
├── Makefile
├── STRUCTURE.md
│
├── core/agentsentrix/
│   ├── bus/
│   │   ├── bus.py                # In-memory pub/sub event bus
│   │   └── cache.py              # Redis state & verdict cache
│   │
│   ├── engine/                   # MultiTierEvaluator & BlastRadiusCalculator
│   ├── policy/                   # YAML Rules & PolicyLoader (Path normalization + Entropy)
│   ├── proxy/                    # MCPProxy & QuarantineManager
│   │
│   └── sensors/                  # Telemetry Ingestion Sensors
│       ├── base.py               # Abstract Sensor base class (start, stop, emit_event)
│       ├── replay.py             # ReplaySensor (.jsonl session replay matching original timing)
│       │
│       └── shim/                 # Shell PATH Shim Interceptor Layer
│           ├── runner.py         # ShimRunner & find_real_binary (Risk evaluation, exec, Ctrl+C & stdin)
│           ├── manager.py        # ShimManager (Cross-platform wrapper generator & PATH wiring)
│           └── bin/              # Shim target binaries (bash, rm, curl, git, aws)
│
├── docs/
│   ├── STAGE1_STATUS_AND_VERIFICATION.md
│   ├── STAGE2_RISK_ENGINE_AND_POLICY_GUIDE.md
│   ├── STAGE3_STATUS_AND_VERIFICATION.md
│   ├── SHELL_SHIM_SENSOR_GUIDE.md
│   └── STAGE4_SHELL_SHIM_AND_INTERCEPTOR_GUIDE.md # (This document)
│
└── tests/
    ├── test_stage1.py            # Stage 1 persistence & bus tests (1 passed)
    ├── test_stage2.py            # Stage 2 risk engine & policy tests (7 passed)
    ├── test_stage3.py            # Stage 3 MCP proxy & transport tests (7 passed)
    └── test_stage3_shim.py       # Shell shim, quarantine & stdin tests (6 passed)
```

---

## 3. Subsystem Architecture & Implementation Details

```
       [ CLI Execution / Agent Subprocess ]  (e.g., rm -rf / or git checkout main)
                         │
                         ▼
        ┌──────────────────────────────────┐
        │  Shim Directory (Front of PATH)  │  (bash, rm, curl, git, aws)
        └────────────────┬─────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │       ShimRunner (runner.py)     │
        └────────────────┬─────────────────┘
                         │
                         ├─► 1. Formulate AgentEvent (sensor: Sensor.SHELL_SHIM)
                         ├─► 2. Evaluate via MultiTierEvaluator
                         ├─► 3. Stream Telemetry to EventBus (DuckDB / JSONL)
                         │
          ┌──────────────┴──────────────┐
   verdict: ALLOWED             verdict: BLOCKED / QUARANTINED
          │                             │
          ▼                             ▼
 [ Resolve Real System Binary ]  [ Print Policy Denial Warning to stderr ]
 (Filtering out shim dir)        [ Exit with Non-Zero Status Code (1) ]
          │
          ▼
 [ Forward Execution & Exit ]
```

### 3.1 Real System Binary Resolution (`find_real_binary`)
To execute allowed commands without triggering recursive infinite loops:
- `find_real_binary(cmd_name)` inspects `os.environ["PATH"]`.
- Explicitly filters out any directory containing `"agentsentrix"` or `"shim"`.
- Searches clean `PATH` for system binary executables (handling Windows `.exe`, `.cmd`, `.bat` extensions).

### 3.2 Interactive Terminal Quarantine & Messaging
When a command triggers `QUARANTINED` (scores 40–74):
1. **Explicit Terminal Waiting Guidance**:
   ```
   [AgentSentrix] Action held for human approval (Event ID: evt_shim_1a2b3c). Resolve at http://localhost:7777...
     Risk Score: 50/100 | Rationale: Ambiguous AWS S3 sync operation
   ```
2. **Operator Rejection**:
   If rejected from the dashboard, prints `[AgentSentrix] QUARANTINE DENIED by operator. Aborting execution.` and returns exit status code `1` without executing the binary.

### 3.3 Ctrl+C / SIGINT Signal Handling
If the developer presses `Ctrl+C` while waiting for quarantine approval:
- Catches `KeyboardInterrupt` / `asyncio.CancelledError`.
- Cleans up quarantine state in Redis via `QuarantineManager.resolve_quarantine(event_id, BLOCKED, "Cancelled by user (Ctrl+C)")`.
- Prints `[AgentSentrix] QUARANTINE CANCELLED by developer (Ctrl+C). Aborting execution.` and exits cleanly with status code `1` (zero python tracebacks).

### 3.4 Standard Input / Pipe Forwarding (`stdin` Passthrough)
Subprocess execution forwards `sys.stdin` directly (`stdin=sys.stdin`), enabling automated pipe tools and input redirection (e.g. `echo "print('hello')" | python` or `git apply - < patch.diff`) without swallowing stdin bytes.

---

## 4. How to Use Stage 4 Components in Code

### 4.1 Installing Shims & Running Commands in Python
```python
import subprocess
from core.agentsentrix.sensors.shim.manager import ShimManager

# 1. Initialize ShimManager and generate binary wrappers
manager = ShimManager()
shim_dir = manager.install_shims()
print(f"Shims installed at: {shim_dir}")

# 2. Obtain environment with shims prepended to PATH
shimmed_env = manager.get_env_with_shims()

# 3. Execute allowed command via subprocess
res_allowed = subprocess.run(["git", "--version"], env=shimmed_env, capture_output=True, text=True)
print("Git Output:", res_allowed.stdout) # Output: git version 2.47.1...

# 4. Attempting a blocked command
res_blocked = subprocess.run(["rm", "-rf", "/"], env=shimmed_env, capture_output=True, text=True)
print("Exit Code:", res_blocked.returncode) # Output: 1
print("Policy Error:\n", res_blocked.stderr)
# Output: [AgentSentrix] POLICY BLOCKED: Shell command 'rm -rf /' was refused.
```

---

## 5. Verification & Testing Handbook

### 5.1 Verify Docker & Redis Status
```powershell
# Check Redis container status
docker ps --filter "name=agentsentrix-redis"

# Verify Redis connectivity from Python
venv\Scripts\python.exe -c "import redis; r = redis.Redis(host='localhost', port=6379); print('Redis Ping:', r.ping())"
```
*Expected Output:* `Redis Ping: True`

### 5.2 Test Shim Installation via Python CLI
```powershell
venv\Scripts\python.exe -c "from core.agentsentrix.sensors.shim.manager import ShimManager; mgr = ShimManager(); d = mgr.install_shims(); print('Shims installed to:', d)"
```

### 5.3 Test Interception via ShimRunner CLI
```powershell
# 1. Test Allowed Command
venv\Scripts\python.exe -m core.agentsentrix.sensors.shim.runner git --version

# 2. Test Blocked Command
venv\Scripts\python.exe -m core.agentsentrix.sensors.shim.runner rm -rf /
```

### 5.4 Run Full Automated System Pytest Suite (All 21 Tests)
```powershell
venv\Scripts\pytest.exe tests/test_stage1.py tests/test_stage2.py tests/test_stage3.py tests/test_stage3_shim.py -v
```

---

## 6. Full System Test Matrix (21 / 21 Passed)

| Test Module | Test Name | Functionality Verified | Result |
| :--- | :--- | :--- | :--- |
| **`test_stage1.py`** | `test_stage1_complete_flow` | Bus delivery, DuckDB table creation, JSONL session appending, Ring Buffer catchup, Redis verdict caching. | `PASSED` |
| **`test_stage2.py`** | `test_shannon_entropy` | High Shannon entropy secret key detection (>3.8). | `PASSED` |
| | `test_tier0_yaml_rules` | YAML policy regex rules matching `.env`, `rm -rf`, `curl \| sh`, safe reads. | `PASSED` |
| | `test_blast_radius_calculator` | Reversibility, secret exposure, egress, and blast radius scoring (0-100). | `PASSED` |
| | `test_multitier_evaluator_full_flow` | Multi-tier evaluation flow & SHA-256 Redis verdict caching. | `PASSED` |
| | `test_resilience_warning_emission` | Offline LLM service warning emission (`UserWarning`) without crashing. | `PASSED` |
| | `test_path_traversal_evasion_prevention` | Path normalization (`normalize_path`) preventing `./subdir/../../.env` evasion. | `PASSED` |
| | `test_tier1_tier2_mock_responses` | Unpacking structured JSON responses from Ollama (50) & Groq (80) in ambiguous band. | `PASSED` |
| **`test_stage3.py`** | `test_mock_mcp_servers` | Target mock Filesystem, Terminal, and Git MCP servers. | `PASSED` |
| | `test_proxy_allowed_flow` | Allowed MCP tool call forwarding & `EventBus` logging. | `PASSED` |
| | `test_proxy_blocked_flow` | Blocked MCP tool call refusal with `isError: True` (Score 100/100). | `PASSED` |
| | `test_proxy_quarantine_resolution_allowed` | Quarantined MCP call freeze on `asyncio.Future` & operator approval unblocking. | `PASSED` |
| | `test_proxy_quarantine_resolution_rejected` | Quarantined MCP call rejection with error payload. | `PASSED` |
| | `test_jsonrpc_stdio_transport` | Stdio JSON-RPC 2.0 wire transport, `tools/list`, `tools/call`, `-32700`, `-32601`. | `PASSED` |
| | `test_quarantine_state_sync_with_redis` | Redis quarantine state sync (`"quarantined"` and `"resolved"`). | `PASSED` |
| **`test_stage3_shim.py`**| `test_shim_manager_installation` | `ShimManager` installation of POSIX scripts and Windows `.cmd` wrappers. | `PASSED` |
| | `test_shim_runner_find_real_binary` | `find_real_binary()` locating system executable while filtering shim path. | `PASSED` |
| | `test_shim_runner_allowed_flow` | Forwarding allowed shell command (`git --version`) & `Sensor.SHELL_SHIM` event emission. | `PASSED` |
| | `test_shim_runner_blocked_flow` | Refusing dangerous shell command (`rm -rf /`) with exit code `1` and `stderr` warning. | `PASSED` |
| | `test_shim_runner_quarantine_flow` | Terminal quarantine waiting message, operator rejection, and clean exit code `1`. | `PASSED` |
| | `test_shim_stdin_passthrough` | `sys.stdin` handle forwarding (`stdin=sys.stdin`) for CLI pipes and input redirection. | `PASSED` |
