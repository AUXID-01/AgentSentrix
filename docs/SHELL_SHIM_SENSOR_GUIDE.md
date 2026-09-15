# AgentSentrix - Shell PATH Shim Sensor Guide

This document provides a complete developer and verification guide for the **Shell PATH Shim Interceptor Layer** of **AgentSentrix** (`core/agentsentrix/sensors/shim/`), which captures direct CLI execution and raw subprocesses (`bash`, `rm`, `curl`, `git`, `aws`) bypassing MCP tool protocols.

---

## 1. Architectural Overview & Workflow

The Shell Shim sensor sits at the front of the operating system's `PATH` environment variable. When an agent or subprocess executes a CLI command, the shim captures execution context before forwarding or blocking.

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

---

## 2. File & Component Breakdown

| File | Purpose & Implementation Details |
| :--- | :--- |
| **[`core/agentsentrix/sensors/base.py`](file:///d:/AgentSentrix/core/agentsentrix/sensors/base.py)** | Abstract `Sensor` base class specifying `start()`, `stop()`, and `emit_event(event)` interfaces for all telemetry sensors. |
| **[`core/agentsentrix/sensors/replay.py`](file:///d:/AgentSentrix/core/agentsentrix/sensors/replay.py)** | `ReplaySensor` that streams historical session events from append-only `.jsonl` files to `EventBus` respecting relative time offsets. |
| **[`core/agentsentrix/sensors/shim/runner.py`](file:///d:/AgentSentrix/core/agentsentrix/sensors/shim/runner.py)** | `ShimRunner` and `find_real_binary()`: <br>• Formulates `AgentEvent` with `sensor = Sensor.SHELL_SHIM` <br>• Evaluates risk via `MultiTierEvaluator.assess()` <br>• Dispatches events to `EventBus` <br>• Resolves system binary on clean `PATH` (skipping shim dir to prevent infinite loops) <br>• Executes allowed calls or blocks dangerous commands with `stderr` policy warning and exit code `1`. |
| **[`core/agentsentrix/sensors/shim/manager.py`](file:///d:/AgentSentrix/core/agentsentrix/sensors/shim/manager.py)** | `ShimManager`: <br>• `install_shims(shim_dir)`: Generates POSIX `#!/bin/sh` scripts and Windows `.cmd` / `.bat` wrappers for `bash`, `rm`, `curl`, `git`, `aws`. <br>• `get_env_with_shims()`: Returns environment dictionary prepending shim directory to `PATH`. |
| **[`tests/test_stage3_shim.py`](file:///d:/AgentSentrix/tests/test_stage3_shim.py)** | Test suite verifying installation, allowed execution forwarding, blocked command refusal, real binary resolution, and `EventBus` telemetry emission. |

---

## 3. How to Use the Shell Shim Layer

### 3.1 Install Shims & Get Shimmed Environment in Python
```python
from core.agentsentrix.sensors.shim.manager import ShimManager
import subprocess

# 1. Initialize ShimManager and install wrappers
manager = ShimManager()
shim_dir = manager.install_shims()
print(f"Shims installed at: {shim_dir}")

# 2. Get environment dictionary with shims prepended to PATH
shimmed_env = manager.get_env_with_shims()

# 3. Run subprocess with shimmed environment
res = subprocess.run(["git", "--version"], env=shimmed_env, capture_output=True, text=True)
print("Git stdout:", res.stdout)

# Attempting a blocked command:
res_blocked = subprocess.run(["rm", "-rf", "/"], env=shimmed_env, capture_output=True, text=True)
print("Exit Code:", res_blocked.returncode) # Output: 1
print("Policy Error:", res_blocked.stderr)
```

---

## 4. Verification & Testing Handbook

### 4.1 Check Docker & Redis Infrastructure
```powershell
# Verify Redis container is running
docker ps --filter "name=agentsentrix-redis"

# Test Redis connection from Python
venv\Scripts\python.exe -c "import redis; r = redis.Redis(host='localhost', port=6379); print('Redis Ping:', r.ping())"
```
*Expected Output:* `Redis Ping: True`

### 4.2 Test Shim Installation via Python CLI
```powershell
venv\Scripts\python.exe -c "from core.agentsentrix.sensors.shim.manager import ShimManager; mgr = ShimManager(); d = mgr.install_shims(); print('Shims installed to:', d)"
```

### 4.3 Test Command Interception via Shim Runner CLI
```powershell
# 1. Allowed Command Test
venv\Scripts\python.exe -m core.agentsentrix.sensors.shim.runner git --version

# 2. Blocked Command Test (refused with non-zero exit code)
venv\Scripts\python.exe -m core.agentsentrix.sensors.shim.runner rm -rf /
```

### 4.4 Run Full System Pytest Suite (All 21 Tests)
```powershell
venv\Scripts\pytest.exe tests/test_stage1.py tests/test_stage2.py tests/test_stage3.py tests/test_stage3_shim.py -v
```

*Expected Output Summary:* `21 passed in 3.53s`

---

## 5. Interactive Terminal & Pipe Edge Case Handling

### 5.1 Explicit Terminal Feedback & Operator Rejection
When a command triggers `QUARANTINED` (scores 40–74):
1. **Explicit Terminal Waiting Message**:
   ```
   [AgentSentrix] Action held for human approval (Event ID: evt_shim_1a2b3c). Resolve at http://localhost:7777...
     Risk Score: 50/100 | Rationale: Ambiguous AWS S3 sync operation
   ```
2. **Operator Denial**:
   If rejected in the dashboard, prints `[AgentSentrix] QUARANTINE DENIED by operator. Aborting execution.` and exits with status code `1`.

### 5.2 Ctrl+C / SIGINT Signal Handling
If the developer presses `Ctrl+C` while waiting for human approval:
- Catches `KeyboardInterrupt` / `asyncio.CancelledError`.
- Cleans up quarantine state in Redis (`resolve_quarantine(event_id, BLOCKED, "Cancelled by user (Ctrl+C)")`).
- Prints `[AgentSentrix] QUARANTINE CANCELLED by developer (Ctrl+C). Aborting execution.` and exits cleanly with status code `1` (zero python tracebacks).

### 5.3 Standard Input / Pipe Forwarding (`stdin` Passthrough)
Subprocess execution forwards `sys.stdin` directly (`stdin=sys.stdin`), enabling automated pipe tools and input redirection (e.g. `echo "print('hello')" | python` or `git apply - < patch.diff`) without swallowing stdin stream bytes.
