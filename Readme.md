# AgentSentrix 🛡️⚡

> **Real-Time Agentic Security Gateway, Multi-Tier Risk Engine & 3D WebGL Threat Visualizer**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.1.1-emerald.svg)](https://pypi.org/project/agentsentrix/)

---

## 💡 What is AgentSentrix?

**AgentSentrix** is an open-source, production-grade security framework designed to protect AI agent workflows (LangGraph, CrewAI, AutoGen, custom Python agents) against **unintended command execution, secret leaks, intent drift, and prompt injection**.

It acts as an inline security firewall that intercepts tool calls, evaluates risk in real-time across a **3-tier scoring pipeline**, suspends dangerous operations in a **Human-in-the-Loop Quarantine**, and streams live 3D telemetry to a WebGL visualizer.

---

## ✨ Key Features

- **⚡ Multi-Tier Risk Pipeline ($T0 \rightarrow T1 \rightarrow T2$)**:
  - **Tier 0 (~1ms)**: Deterministic YAML security policies & Shannon entropy secret detection.
  - **Tier 1 (~50ms)**: Local Ollama model checking prompt injection & intent drift.
  - **Tier 2 (~300ms)**: Groq LLM-as-a-Judge evaluating ambiguous risk scores ($30–70$).
- **🛑 Human-in-the-Loop Quarantine**: High-risk actions automatically pause agent execution until approved or blocked by a security operator via the dashboard.
- **🔌 Flexible Interception Sensors**:
  - **Python SDK Middleware**: Wrap any Python tool call or function with a single decorator `@sentrix.intercept_tool()`.
  - **MCP Proxy**: Translucent Stdio/SSE proxy intercepting Model Context Protocol (MCP) server calls.
  - **Shell Shim**: CLI binary wrapper intercepting raw bash/powershell terminal executions.
- **🌐 3D WebGL Threat Visualizer Dashboard**: Next.js 14 + WebGL 3D canvas rendering live topology, particle beams, composite risk gauges, and drilldown context drawers.
- **📊 ML Observability & Big-Data Analytics**: Integrated MLflow tracking ($T0/T1/T2$ metrics, false positives) and zero-copy DuckDB-to-Parquet export for PySpark analytics.

---

## 🚀 Quickstart — Developer Python SDK

### 1. Install `agentsentrix`
```bash
pip install agentsentrix
```

### 2. Wrap Agent Tools with `@sentrix.intercept_tool()`
```python
import asyncio
import subprocess
from agentsentrix import AgentSentrixSDK, SecurityBlockError

# Initialize SDK pointing to local or cloud AgentSentrix Security Gateway
sentrix = AgentSentrixSDK(server_url="http://localhost:8000", fail_safe=True)

# Wrap any agent tool or function
@sentrix.intercept_tool(agent_id="my-langgraph-agent", action_type="shell_exec")
async def execute_command(command: str):
    # 1. SDK sends action payload to AgentSentrix Gateway
    # 2. If risk is high, execution SUSPENDS waiting for human approval on the dashboard
    # 3. If BLOCKED, raises SecurityBlockError
    return subprocess.run(command, shell=True, capture_output=True, text=True).stdout

async def main():
    try:
        output = await execute_command("cat src/main.py")
        print("Command Output:", output)
    except SecurityBlockError as err:
        print("Security Alert:", err)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔌 Alternative Interception Methods

### Option A: MCP (Model Context Protocol) Server Proxy
Point your `mcp.json` config at the AgentSentrix Proxy:
```json
{
  "mcpServers": {
    "git-sync": {
      "command": "agentsentrix-proxy",
      "args": ["--target", "npx", "-y", "@modelcontextprotocol/server-git"]
    }
  }
}
```

### Option B: Terminal Shell Shim
Intercept terminal binaries (e.g. `curl`, `git`, `bash`) automatically:
```bash
agentsentrix shim install --binary git
```

---

## 🖥️ Running the AgentSentrix Core Server & 3D Visualizer

### 1. Start the Security Gateway Server
```bash
python -m core.agentsentrix.server.app
# Security Gateway active at http://localhost:8000
```

### 2. Launch the 3D Threat Visualizer Dashboard
```bash
cd dashboard
npm run dev
# Dashboard active at http://localhost:3000
```

### 3. Run the Multi-Agent Simulation Benchmark
```bash
python -m sim.runner
```

### 4. Launch MLflow Observability UI
```bash
mlflow ui --port 5000 --backend-store-uri sqlite:///mlflow.db
# MLflow UI active at http://localhost:5000
```

### 5. Run Parquet Security Analytics
```bash
python -m analytics.pyspark_analytics
```

---

## 📊 Multi-Tier Risk Engine Architecture

```text
               +-------------------------------------------------+
               |             Agent Tool Execution                |
               +-------------------------------------------------+
                                       |
                                       v
               +-------------------------------------------------+
               |   Tier 0: YAML Policy Rules & Shannon Entropy  | (~1ms)
               +-------------------------------------------------+
                                       |
                     +-----------------+-----------------+
                     |                                   |
           High Confidence Hit                    Ambiguous Band
           (Score <=20 or >=75)                     (Score 30-70)
                     |                                   |
                     v                                   v
             [Fast-Path Exit]            +-------------------------------+
                                         | Tier 1: Local Ollama Model    | (~50ms)
                                         +-------------------------------+
                                                         |
                                                         v
                                         +-------------------------------+
                                         | Tier 2: Groq LLM-as-a-Judge   | (~300ms)
                                         +-------------------------------+
                                                         |
                                                         v
                                              [Composite Final Score]
                                                         |
          +----------------------------------------------+----------------------------------------------+
          |                                              |                                              |
          v                                              v                                              v
   [Verdict: ALLOWED]                          [Verdict: QUARANTINED]                        [Verdict: BLOCKED]
  (Execution Proceeds)                     (Suspends Awaiting Operator)                   (SecurityBlockError Raised)
```

---

## 🧪 Testing Suite

Run the full automated pytest suite:
```bash
pytest tests/ -v
```

---

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for more information.