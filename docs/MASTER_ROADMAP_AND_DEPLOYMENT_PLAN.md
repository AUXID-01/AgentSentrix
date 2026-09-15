# AgentSentrix — Master Execution Plan & Cloud Deployment Roadmap

> **Targeting Production PyPI Release `v0.2.0` & Live Hosted Cloud Security Gateway**
> **Date**: September 16, 2026 | **Author**: AgentSentrix Core Engineering Team

---

## 🌐 1. The Global Developer Experience (The Target Product Flow)

Imagine a developer anywhere in the world (San Francisco, Tokyo, London, Bangalore) building a **Multi-Agent Flight Booking System** (LangGraph, CrewAI, AutoGen, or custom Python agents).

### The Complete 3-Step Flow:

```text
[ Developer's Machine (Anywhere in the World) ]
  1. Installs SDK:      pip install agentsentrix
  2. Runs Application:  agentsentrix run python main.py
                                │
                                │ Zero-Touch Interception Streams HTTPS Telemetry
                                v
 ┌────────────────────────────────────────────────────────────────────────┐
 │            OUR LIVE CLOUD PLATFORM (https://api.agentsentrix.io)        │
 │                                                                        │
 │  • Central FastAPI Gateway & Async EventBus Pipeline                   │
 │  • Multi-Tier Risk Engine (Tier 0 Rules, Ollama, Groq LLM-as-a-Judge)  │
 │  • HITL Quarantine Manager (Suspends dangerous actions in real-time)  │
 │  • DuckDB & MLflow Cloud Analytics Storage                             │
 └────────────────────────────────────────────────────────────────────────┘
                                │
                                │ Live 3D WebGL Telemetry Streaming (WSS)
                                v
 ┌────────────────────────────────────────────────────────────────────────┐
 │           OUR LIVE 3D VISUALIZER (https://dashboard.agentsentrix.io)   │
 │                                                                        │
 │  • WebGL 3D Force-Directed Multi-Agent Topology Canvas                 │
 │  • Real-Time Risk Index Radial Gauge (0–100)                           │
 │  • Live Event Feed & Multi-Agent Call Stack Lineage                    │
 │  • Interactive [Approve Action] & [Block Action] Quarantine Buttons    │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 2. Detailed Master TODO Roadmap (Phase-by-Phase)

To deliver this exact global product flow, here is the minute, step-by-step TODO plan:

### PHASE 1: Zero-Touch CLI Interception Wrapper (`agentsentrix run`)
> **Goal**: Allow developers to protect any single-agent or multi-agent Python system with ZERO code modifications.

- [ ] **TODO 1.1**: Create `core/agentsentrix/sensors/patcher.py`.
  - Implement runtime monkey-patching for standard Python modules:
    - `subprocess.Popen`, `subprocess.run`, `os.system` (Shell Executions)
    - `builtins.open` (File Reads & Writes)
    - `httpx.AsyncClient`, `requests.Session` (Network Egress)
    - Framework hooks for `langchain`, `crewai`, `autogen`, `langgraph`.
- [ ] **TODO 1.2**: Implement Agent Persona Auto-Discovery.
  - Automatically extract agent role/name from agent class instances or thread names and assign `agent_id` (e.g., `SearchAgent`, `PaymentAgent`).
  - Generate and inject monotonic `parent_id` header to capture cross-agent handoffs and call-stack lineage.
- [ ] **TODO 1.3**: Wire CLI command `agentsentrix run <cmd>`.
  - Update `core/agentsentrix/cli.py` so `agentsentrix run python main.py` activates `patcher.py` before executing the user's script.

---

### PHASE 2: Synchronous Evaluation & Quarantine Endpoint (`POST /evaluate`)
> **Goal**: Fix the server verdict parsing logic so `SecurityBlockError` is enforced and `QUARANTINED` actions pause execution in real time.

- [ ] **TODO 2.1**: Implement `POST /evaluate` endpoint in `core/agentsentrix/server/routes.py`.
  - Accept `AgentEvent` payload.
  - Execute `evaluator.assess(event)` synchronously.
  - If verdict is `BLOCKED`: Immediately return `{"verdict": "blocked", "score": score, "rationale": rationale}`.
  - If verdict is `QUARANTINED`: Register event with `quarantine_mgr.register_quarantine(event.id)` and `await` the future until an operator clicks **Approve** or **Block** on the 3D Dashboard (or timeout).
  - Return JSON: `{"verdict": "allowed" | "quarantined" | "blocked", "score": score, "rationale": rationale}`.
- [ ] **TODO 2.2**: Update `core/agentsentrix/sdk.py`.
  - Update `_evaluate_async` and `_evaluate_sync` to call `POST /evaluate`.
  - Parse response verdict:
    - If `"blocked"` $\rightarrow$ raise `SecurityBlockError(rationale)`.
    - If `"quarantined"` $\rightarrow$ handle resolution.
    - If `"allowed"` $\rightarrow$ proceed with execution.

---

### PHASE 3: Embedded Local Tier 0 Guardrail (Offline Protection)
> **Goal**: Ship embedded offline protection inside `pip install agentsentrix` so developers get immediate value even with zero server setup.

- [ ] **TODO 3.1**: Bundle Tier 0 Policy Loader inside the SDK package.
  - Include default security rules (`rules.yaml`) and **Shannon entropy secret detector** directly in `core/agentsentrix/policy/`.
- [ ] **TODO 3.2**: Add In-Process Fallback Evaluation in `sdk.py`.
  - If `server_url` is offline or unreachable, execute local Tier 0 evaluation in-process:
    - Instantly block `rm -rf /`, `.env` secret reads, AWS credential leaks, and high-entropy secret outputs **without crashing the agent**.

---

### PHASE 4: Cloud Infrastructure & SaaS Deployment (Our Brain + 3D Dashboard)
> **Goal**: Deploy our backend server and 3D Visualizer live to the cloud so any developer in the world can connect out-of-the-box.

- [ ] **TODO 4.1**: Dockerize the Entire Gateway & Dashboard.
  - Finalize `docker/Dockerfile` multi-stage build compiling Next.js frontend into `core/agentsentrix/web/` and packaging FastAPI + Uvicorn.
  - Verify standalone execution: `docker run -p 8000:8000 agentsentrix:latest`.
- [ ] **TODO 4.2**: Provision Cloud Infrastructure.
  - Provision Cloud Server (AWS EC2 / DigitalOcean / Render / GCP).
  - Configure Domain Name (`api.agentsentrix.io`) & Let's Encrypt SSL Certificates (`https://`).
  - Deploy Redis container for shared state caching across multi-agent sessions.
  - Deploy hosted MLflow tracking instance.
- [ ] **TODO 4.3**: Multi-Tenant API Key Authentication.
  - Add API key headers (`Authorization: Bearer sk_live_...`) to `POST /evaluate` and `POST /events/ingest`.
  - Create developer workspace isolation in DuckDB/Postgres.

---

### PHASE 5: PyPI Package Release (`v0.2.0`) & Global Documentation
> **Goal**: Publish version `0.2.0` on PyPI and publish clear testing guides.

- [ ] **TODO 5.1**: Update SDK default gateway URL in `sdk.py`:
  ```python
  server_url: str = "https://api.agentsentrix.io"
  ```
- [ ] **TODO 5.2**: Bump version to `0.2.0` in `pyproject.toml` and `core/agentsentrix/__init__.py`.
- [ ] **TODO 5.3**: Build and upload distributions to PyPI:
  ```powershell
  python -m build
  twine upload dist/agentsentrix-0.2.0*
  ```
- [ ] **TODO 5.4**: Publish Global Quickstart Video & Documentation.

---

## 📅 Minute Technical Task Matrix

| Task ID | Task Description | Target File | Priority |
|---|---|---|---|
| **T-101** | Create zero-touch monkey patcher for subprocess/os/builtins | `core/agentsentrix/sensors/patcher.py` | **HIGH** |
| **T-102** | Add `agentsentrix run` command handler | `core/agentsentrix/cli.py` | **HIGH** |
| **T-201** | Implement synchronous `POST /evaluate` endpoint | `core/agentsentrix/server/routes.py` | **CRITICAL** |
| **T-202** | Fix verdict parsing & `SecurityBlockError` raising in SDK | `core/agentsentrix/sdk.py` | **CRITICAL** |
| **T-301** | Embed Tier 0 policy loader & Shannon entropy in SDK package | `core/agentsentrix/policy/loader.py` | **HIGH** |
| **T-401** | Finalize multi-stage Docker build for Gateway + WebGL SPA | `docker/Dockerfile` | **HIGH** |
| **T-402** | Deploy Cloud Gateway on AWS/Render with SSL | `https://api.agentsentrix.io` | **HIGH** |
| **T-501** | Publish `agentsentrix v0.2.0` to PyPI | `dist/agentsentrix-0.2.0*` | **HIGH** |
