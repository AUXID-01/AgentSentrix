# AgentSentrix — Developer SDK & System Integration Guide

This document is the definitive guide for developers, engineering teams, and package maintainers integrating **AgentSentrix** into AI coding agents, LangGraph workflows, MCP servers, and terminal environments.

---

## 1. Executive Summary & Core Philosophy

**AgentSentrix** acts as an in-line security firewall and real-time threat monitor for autonomous AI coding agents (Claude Code, Cursor, LangGraph, AutoGen, CrewAI).

### Key Architectural Principles
1. **Zero-Friction Developer Experience**: Developers do NOT need to write manual decorators around every tool function. Integration takes 1 line of code or zero code via CLI.
2. **Fully Decoupled Architecture**: The 3D WebGL Dashboard (`dashboard/`), API Server (`server/`), and Risk Evaluator (`engine/`) are completely decoupled from specific agent frameworks.
3. **Adaptive 3-Tier Risk Engine**: Operates out-of-the-box with **zero API keys** (Tier 0 rules), and automatically upgrades if local Ollama or cloud Groq keys are added to `.env`.

---

## 2. The 4 Developer Integration Methods

### Method 1: The 1-Line Global Hook (`agentsentrix.init()`)
**Best for**: Any Python script, microservice, or custom AI agent workflow.

Developers add **one single line** at the top of their entry-point file (`main.py`):

```python
import agentsentrix

# Initialize AgentSentrix global runtime hooks
agentsentrix.init(server_url="http://localhost:8000")

# Everything below this line is automatically protected!
# Subprocesses, file operations, and tool calls are intercepted in real time.
```

#### How it works:
`agentsentrix.init()` installs lightweight runtime hooks into Python's `subprocess.run`, `os.system`, `asyncio.create_subprocess_exec`, and standard tool execution registries.

---

### Method 2: Zero-Code CLI Command Wrapper (`agentsentrix run`)
**Best for**: Terminal execution, shell scripts, Claude Code, Cursor, or existing Python scripts where modifying source code is not desired.

Zero code changes are required. The developer simply runs their agent via CLI:

```bash
# Wrap a Python agent script
agentsentrix run python my_langgraph_agent.py

# Wrap Claude Code CLI
agentsentrix run claude

# Wrap Cursor IDE agent tasks
agentsentrix run cursor
```

#### How it works:
`agentsentrix run` uses the **Shell Shim Manager** (`sensors/shim/manager.py`). It injects executable wrappers into the process environment PATH. Any command executed by the agent (`git`, `curl`, `python`, `rm`, `pytest`) is intercepted at the OS process level before execution.

---

### Method 3: Native LangGraph / LangChain Callback Handler
**Best for**: Developers building agents using `langgraph` or `langchain`.

Developers pass **one callback parameter** when building their agent state graph:

```python
from langgraph.prebuilt import create_react_agent
from agentsentrix.integrations.langchain import AgentSentrixCallbackHandler

agent = create_react_agent(
    model=llm,
    tools=tools,
    callbacks=[AgentSentrixCallbackHandler(server_url="http://localhost:8000")]
)
```

#### How it works:
`AgentSentrixCallbackHandler` hooks natively into LangChain/LangGraph's `on_tool_start` event. When the LLM chooses any tool to run, the callback evaluates security risk, streams telemetry to the **3D Dashboard**, and holds execution in **Quarantine** if dangerous.

---

### Method 4: Industry-Standard MCP Proxy (`mcp.json`)
**Best for**: Claude Code, Cursor, Windsurf, or any Model Context Protocol (MCP) server.

Developers update their standard `mcp.json` file to route tool calls through `agentsentrix-proxy`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "agentsentrix-proxy",
      "args": [
        "--target-command", "npx -y @modelcontextprotocol/server-filesystem /path/to/repo",
        "--server-url", "http://localhost:8000"
      ]
    }
  }
}
```

#### How it works:
`agentsentrix-proxy` acts as a transparent stdio JSON-RPC 2.0 proxy. It intercepts `tools/call` requests, passes them through the multi-tier risk engine, and forwards approved requests to the target MCP server.

---

## 3. Adaptive 3-Tier Risk Engine & `.env` Setup

AgentSentrix risk evaluation ([`core/agentsentrix/engine/evaluator.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/engine/evaluator.py)) automatically adapts based on what is available in `.env`:

```env
# AgentSentrix Gateway URL
AGENT_SENTRIX_SERVER=http://localhost:8000

# Tier 1 Local LLM (Optional — Free Local Inference)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest

# Tier 2 Cloud LLM (Optional — Deep LLM-as-a-Judge)
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### Risk Evaluation Tiers
1. **Tier 0 (~1ms — Zero API Keys / Zero Cost)**: Evaluates deterministic YAML security rules (`rules.yaml`) and Shannon entropy. Catches path evasions (`../`), sensitive file access (`.env`, `shadow`, `/etc/passwd`), obfuscated base64, and credentials.
2. **Tier 1 (~50ms — Local Ollama)**: Queries local Ollama endpoint (`llama3.2:latest`) for prompt-injection and intent-drift scoring. If Ollama is offline, emits a non-fatal `UserWarning` and falls back cleanly.
3. **Tier 2 (~300ms — Groq Cloud API)**: Queries Groq `llama-3.3-70b-versatile` for ambiguous risk scores (30–70). If `GROQ_API_KEY` is not present, emits a non-fatal `UserWarning` and uses Tier 0 scores.

---

## 4. Human-in-the-Loop Quarantine Lifecycle

When an agent action receives a high risk score (40–74 = Quarantined, >=75 = Blocked):

```
[ Developer's Agent ]                     [ AgentSentrix Server ]                   [ 3D Dashboard UI ]
         │                                          │                                        │
         │ (1) Agent calls tool                     │                                        │
         ├─────────────────────────────────────────►│                                        │
         │  POST /events/ingest                     │                                        │
         │                                          │ (2) MultiTierEvaluator scores risk     │
         │                                          │     Verdict: QUARANTINED               │
         │                                          │     Creates asyncio.Future (Holding)   │
         │                                          │                                        │
         │                                          │ (3) Broadcasts WsEnvelope              │
         │                                          ├───────────────────────────────────────►│
         │                                          │                                        │ Canvas pulses amber ring
         │                                          │                                        │ Operator inspects call stack
         │                                          │                                        │ Operator clicks [Approve] / [Block]
         │                                          │ (4) Operator decision POST /decide     │
         │                                          │◄───────────────────────────────────────┤
         │                                          │                                        │
         │ (5) SDK receives decision                │                                        │
         │◄─────────────────────────────────────────┤                                        │
         │     Resolves asyncio.Future              │                                        │
         │                                          │                                        │
         ▼                                          ▼                                        ▼
 [ Tool Executes / Denied ]               [ Persisted to DuckDB ]                  [ Canvas glows Green / Red ]
```

1. **Suspension**: The SDK / Proxy sends `POST /events/ingest` and holds execution via `asyncio.Future`.
2. **Real-time Alert**: The event streams over WebSockets to `http://localhost:3000`. The 3D Threat Canvas pulses an amber warning ring around the agent node.
3. **Operator Decision**:
   - Clicking **✓ APPROVE ACTION**: `POST /decide` resolves the future to `allowed`. The tool executes cleanly.
   - Clicking **✕ BLOCK ACTION**: `POST /decide` resolves the future to `blocked`. The SDK raises `PolicyViolationError`, blocking execution.

---

## 5. Developer Cheat-Sheet Summary

| Use Case | Integration Method | Setup Effort |
| :--- | :--- | :--- |
| **Python Script / Agent** | `import agentsentrix; agentsentrix.init()` | 1 line at top of file |
| **Terminal / Claude / Cursor** | `agentsentrix run python agent.py` | 0 lines changed |
| **LangGraph / LangChain** | `callbacks=[AgentSentrixCallbackHandler()]` | 1 parameter in agent creation |
| **Claude Code / Cursor MCP** | Add `agentsentrix-proxy` to `mcp.json` | 1 JSON entry |
