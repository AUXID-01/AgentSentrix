# AgentSentrix Folder Structure & File Purpose Guide

This document explains the purpose and architecture requirement of every file and directory in the **AgentSentrix** codebase.

```
agentsentrix/
├── pyproject.toml
├── AGENTS.md
├── Makefile
├── STRUCTURE.md
│
├── core/agentsentrix/
│   ├── cli.py                    # typer: init | up | replay | record
│   ├── config.py                 # pydantic-settings, env + agentsentrix.toml
│   │
│   ├── schema/                   # ⚠ THE CONTRACT — no logic, no imports from siblings
│   │   ├── enums.py
│   │   ├── events.py             # AgentEvent, RiskAssessment, BlastRadius
│   │   ├── graph.py              # GraphNode, GraphLink, GraphSnapshot
│   │   └── ws.py                 # WsEnvelope + message types
│   │
│   ├── bus/
│   │   ├── bus.py                # async pub/sub, ring buffer, seq counter
│   │   └── sinks/
│   │       ├── base.py           # Sink protocol
│   │       ├── duckdb_sink.py
│   │       └── jsonl_sink.py     # append-only, feeds replay
│   │
│   ├── engine/
│   │   ├── base.py               # RiskEngine protocol ← Phase 3 swaps behind this
│   │   └── stub.py               # keyword scoring
│   │
│   ├── projection/
│   │   └── graph_projection.py   # event stream → nodes + links
│   │
│   ├── sensors/
│   │   ├── base.py               # Sensor ABC
│   │   └── replay.py             # jsonl → bus, honours original timing
│   │
│   ├── server/
│   │   ├── app.py                # FastAPI assembly + lifespan wiring
│   │   ├── ws.py                 # ConnectionManager
│   │   ├── routes.py             # REST: /health /events /graph /decide
│   │   └── static.py             # serves dashboard/out
│   │
│   └── web/                      # ← built Next.js copied here at package time
│
├── dashboard/
│   ├── app/page.tsx
│   ├── components/
│   │   ├── ThreatCanvas.tsx      # react-force-graph-3d
│   │   ├── EventFeed.tsx
│   │   ├── RiskGauge.tsx
│   │   └── Drilldown.tsx         # stub in Phase 1
│   ├── lib/
│   │   ├── ws.ts                 # reconnecting client
│   │   ├── graphReducer.ts       # mirrors graph_projection.py
│   │   └── colors.ts             # verdict → colour, single source
│   └── types/events.ts           # ← generated, never hand-edited
│
├── data/seed/demo_session.jsonl
├── tests/fixtures/golden_event.json
└── sim/  docker/  analytics/     # empty until later phases
```

---

## Detailed File Responsibilities

### 1. Root Directory

- **[`pyproject.toml`](file:///c:/agent_sentrix/AgentSentrix/pyproject.toml)**: Python project configuration file managing packaging metadata, dependencies (Typer, Pydantic-Settings, FastAPI, DuckDB), entry points, and developer tool settings (mypy, ruff, pytest).
- **[`AGENTS.md`](file:///c:/agent_sentrix/AgentSentrix/AGENTS.md)**: Directives and architectural rules for AI agentic assistants working within this codebase.
- **[`Makefile`](file:///c:/agent_sentrix/AgentSentrix/Makefile)**: Task automation file containing build scripts, testing macros, server startup commands, and package build targets.
- **[`STRUCTURE.md`](file:///c:/agent_sentrix/AgentSentrix/STRUCTURE.md)**: Architectural reference document (this file) outlining project structure and component responsibilities.

---

### 2. Core Python Engine (`core/agentsentrix/`)

- **[`core/agentsentrix/cli.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/cli.py)**: Command-line interface built with `typer` implementing core commands:
  - `init`: Sets up configuration and workspace environment.
  - `up`: Launches server and dashboard services.
  - `replay`: Streams event logs from `.jsonl` files through the bus.
  - `record`: Records event streams to disk.
- **[`core/agentsentrix/config.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/config.py)**: Centralized configuration management using `pydantic-settings`, unifying environment variables (`.env`) and `agentsentrix.toml`.

#### `schema/` (Data Models & Contracts)
> ⚠ **STRICT CONTRACT**: Contains pure data definitions with no business logic and no imports from sibling modules (`bus`, `engine`, `server`, etc.).

- **[`core/agentsentrix/schema/enums.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/schema/enums.py)**: Central enumerations for risk categories, verdicts, event levels, and state types.
- **[`core/agentsentrix/schema/events.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/schema/events.py)**: Telemetry data structures including `AgentEvent`, `RiskAssessment`, and `BlastRadius`.
- **[`core/agentsentrix/schema/graph.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/schema/graph.py)**: Topology representations defining `GraphNode`, `GraphLink`, and `GraphSnapshot`.
- **[`core/agentsentrix/schema/ws.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/schema/ws.py)**: WebSocket communication models defining `WsEnvelope` and real-time payload wrappers.

#### `bus/` (Event Pipeline)
- **[`core/agentsentrix/bus/bus.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/bus/bus.py)**: In-memory asynchronous pub/sub event bus featuring a ring buffer and sequence counter for real-time event dispatch.
- **[`core/agentsentrix/bus/sinks/base.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/bus/sinks/base.py)**: `Sink` protocol interface defining standard methods for all event persistence backends.
- **[`core/agentsentrix/bus/sinks/duckdb_sink.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/bus/sinks/duckdb_sink.py)**: Analytical event sink persisting events into DuckDB for fast SQL queries.
- **[`core/agentsentrix/bus/sinks/jsonl_sink.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/bus/sinks/jsonl_sink.py)**: Append-only file sink outputting JSON Lines formatted event logs (used for replays).

#### `engine/` (Risk Evaluation)
- **[`core/agentsentrix/engine/base.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/engine/base.py)**: Abstract `RiskEngine` protocol contract allowing modular replacement of risk evaluation strategies in future phases.
- **[`core/agentsentrix/engine/stub.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/engine/stub.py)**: Baseline risk evaluation implementation utilizing rule-based and keyword scoring.

#### `projection/` (State Transformation)
- **[`core/agentsentrix/projection/graph_projection.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/projection/graph_projection.py)**: Stateful transformer converting flat incoming `AgentEvent` streams into graph node and link relationships (`GraphSnapshot`).

#### `sensors/` (Telemetry Ingestion)
- **[`core/agentsentrix/sensors/base.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/sensors/base.py)**: Abstract Base Class (`Sensor`) defining event ingestion stream sources.
- **[`core/agentsentrix/sensors/replay.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/sensors/replay.py)**: Ingestion sensor that reads historical `.jsonl` session files and emits events to the bus while matching original timing offsets.

#### `server/` (API & Web Gateway)
- **[`server/app.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/server/app.py)**: FastAPI application factory, middleware configuration, and lifecycle (startup/shutdown) management.
- **[`server/ws.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/server/ws.py)**: `ConnectionManager` handling WebSocket subscriptions, broadcasts, and heartbeat mechanisms.
- **[`server/routes.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/server/routes.py)**: REST API routes (`/health`, `/events`, `/graph`, `/decide`).
- **[`server/static.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/server/static.py)**: Static file server mounting the compiled frontend assets.

#### `web/`
- Directory reserved for housing the compiled static export of the Next.js dashboard at package build time.

---

### 3. Dashboard Frontend (`dashboard/`)

- **[`dashboard/app/page.tsx`](file:///c:/agent_sentrix/AgentSentrix/dashboard/app/page.tsx)**: Main Next.js application page mounting layout components, graph canvases, and event feeds.

#### `dashboard/components/`
- **[`dashboard/components/ThreatCanvas.tsx`](file:///c:/agent_sentrix/AgentSentrix/dashboard/components/ThreatCanvas.tsx)**: Interactive 3D graph visualization component using `react-force-graph-3d`.
- **[`dashboard/components/EventFeed.tsx`](file:///c:/agent_sentrix/AgentSentrix/dashboard/components/EventFeed.tsx)**: Dynamic, real-time scrolling feed displaying live system events.
- **[`dashboard/components/RiskGauge.tsx`](file:///c:/agent_sentrix/AgentSentrix/dashboard/components/RiskGauge.tsx)**: Radial gauge component displaying current composite risk score and verdict.
- **[`dashboard/components/Drilldown.tsx`](file:///c:/agent_sentrix/AgentSentrix/dashboard/components/Drilldown.tsx)**: Detailed inspection drawer/modal stub for analyzing specific nodes and events.

#### `dashboard/lib/`
- **[`dashboard/lib/ws.ts`](file:///c:/agent_sentrix/AgentSentrix/dashboard/lib/ws.ts)**: Reconnecting WebSocket client managing frontend server connection resilience.
- **[`dashboard/lib/graphReducer.ts`](file:///c:/agent_sentrix/AgentSentrix/dashboard/lib/graphReducer.ts)**: Client-side state reducer mirroring backend `graph_projection.py` logic.
- **[`dashboard/lib/colors.ts`](file:///c:/agent_sentrix/AgentSentrix/dashboard/lib/colors.ts)**: Single source of truth for mapping risk verdicts to UI theme color palettes.

#### `dashboard/types/`
- **[`dashboard/types/events.ts`](file:///c:/agent_sentrix/AgentSentrix/dashboard/types/events.ts)**: TypeScript type definitions generated from Python Pydantic schemas (never edited manually).

---

### 4. Data, Testing & Extension Modules

- **[`data/seed/demo_session.jsonl`](file:///c:/agent_sentrix/AgentSentrix/data/seed/demo_session.jsonl)**: Sample dataset of agent events for demo sessions and offline replays.
- **[`tests/fixtures/golden_event.json`](file:///c:/agent_sentrix/AgentSentrix/tests/fixtures/golden_event.json)**: Canonical benchmark `AgentEvent` payload for unit testing schema validation.
- **`sim/`**: Reserved directory for agent simulation environment modules.
- **`docker/`**: Reserved directory for container definitions and Dockerfile configs.
- **`analytics/`**: Reserved directory for offline batch analysis scripts.
