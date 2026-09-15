# AgentSentrix SDK — Capability Verification & Testing Guide

> **Step-by-Step Guide for Developers to Test All AgentSentrix Guardrails after `pip install agentsentrix`**

---

## 1. Prerequisites & Installation

In your Python environment, install `agentsentrix`:

```bash
pip install agentsentrix
```

Ensure the AgentSentrix Gateway Server is running (either locally or on a remote server):

```bash
# Start AgentSentrix Security Gateway Server
agentsentrix server
# Server active at http://localhost:8000
```

---

## 2. Testing All SDK Capabilities (Run 1-Line Script)

Create a test script named `test_sentrix.py` (or run [`examples/sdk_quickstart_demo.py`](file:///c:/agent_sentrix/AgentSentrix/examples/sdk_quickstart_demo.py)):

```python
import asyncio
from agentsentrix import AgentSentrixSDK, SecurityBlockError

# Step 1: Initialize SDK
sentrix = AgentSentrixSDK(server_url="http://localhost:8000", fail_safe=True)

# Test 1: Safe Action (Allowed)
@sentrix.intercept_tool(agent_id="refactorer-01", action_type="file_read")
async def read_code():
    return "Code read successfully."

# Test 2: Dangerous Secret Leak (Blocked)
@sentrix.intercept_tool(agent_id="rogue-01", action_type="file_read")
async def read_secrets():
    return "AWS_SECRET_KEY=abc123xyz"

async def main():
    print("--- 1. Testing Safe Action ---")
    res1 = await read_code()
    print("Result:", res1)  # Output: Code read successfully.

    print("\n--- 2. Testing Secret Exfiltration ---")
    try:
        await read_secrets()
    except SecurityBlockError as err:
        print("BLOCKED BY GUARDRAIL:", err)  # Output: Action BLOCKED by AgentSentrix security policy.

if __name__ == "__main__":
    asyncio.run(main())
```

Run the script:
```bash
python test_sentrix.py
```

---

## 3. What Each Test Verifies

| Test Case | Agent Action | Expected Behavior | SDK Output |
|---|---|---|---|
| **1. Safe Action** | Reading `src/main.py` | Tier 0 Fast-Path Exit ($\approx 1\text{ms}$). Action proceeds normally. | `Code read successfully.` |
| **2. Secret Exfiltration** | Reading `.env` or `AWS credentials` | Blocked by Tier 0 Shannon Entropy & YAML Policy ($Score \ge 75$). | `SecurityBlockError: Action BLOCKED by AgentSentrix policy.` |
| **3. High Risk Action** | Modifying core files or untrusted git clone | Suspends in Quarantine awaiting operator decision on `http://localhost:3000`. | Suspended until operator clicks **Approve** or **Block**. |
| **4. Server Offline** | Server stopped (`fail_safe=True`) | Logs warning and allows execution cleanly without crashing agent. | `UserWarning: AgentSentrix server unreachable... Fail-safe mode allowing action.` |

---

## 4. Visualizing Interception Live on the 3D Dashboard

While running your agents:
1. Open **`http://localhost:3000`** in your browser.
2. Every tool call intercepted by `@sentrix.intercept_tool()` appears instantly on the 3D topology map:
   - Green particle beams = **ALLOWED**
   - Red shields = **BLOCKED**
   - Amber pulsing rings = **QUARANTINED** (click **Approve** or **Block** buttons to resolve).
