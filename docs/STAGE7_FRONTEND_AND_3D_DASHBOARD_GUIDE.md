# Stage 7 — Frontend: Next.js 3D Threat Visualizer Dashboard Guide

This document details the architecture, component implementation, and verification workflow for **Stage 7** (Next.js 3D Threat Visualizer Command Center) in `dashboard/`.

---

## 1. Overview & Architecture

Stage 7 completes the user interface layer of AgentSentrix by providing a real-time, glassmorphic 3D security command center built with **Next.js 14**, **React 18**, **Three.js**, **`react-force-graph-3d`**, and **Tailwind CSS**.

### Key System Responsibilities
1. **Reconnecting WebSocket Stream (`ws.ts`)**: Connects to `ws://localhost:8000/ws` with exponential backoff and resume support via `?since=<seq>`.
2. **Topology Reducer (`graphReducer.ts`)**: Translates backend `GraphSnapshot` projections and incoming `AgentEvent` telemetry into dynamic 3D node and link graph state.
3. **3D WebGL Threat Canvas (`ThreatCanvas.tsx`)**: Renders force-directed graph with custom Three.js geometries (agent icosahedrons, translucent action spheres scaled by risk, and red wireframe shields for blocked threats).
4. **Live Telemetry Feed (`EventFeed.tsx`)**: Scrolling log feed with verdict filter buttons (`All`, `Allowed`, `Quarantined`, `Blocked`).
5. **Composite Risk Gauge (`RiskGauge.tsx`)**: Radial SVG gauge reflecting real-time system risk score (0-100) and threat counters.
6. **Context Inspection Drawer (`Drilldown.tsx`)**: Side drawer displaying `parent_id` call stack lineage, target resource, exact triggered YAML policy rules, blast radius breakdown, and interactive **Approve / Deny** buttons calling `POST /decide`.

---

## 2. Directory & File Inventory

```
dashboard/
├── package.json               # Package dependencies (next, react, react-force-graph-3d, three, tailwindcss)
├── tsconfig.json              # TypeScript configuration
├── next.config.mjs            # Next.js static build export configuration (`output: 'export'`)
├── postcss.config.mjs         # PostCSS configuration for Tailwind
├── tailwind.config.ts         # Dark mode glassmorphic cybersecurity theme
├── app/
│   ├── globals.css            # Global CSS, glassmorphism utilities, scrollbar styling
│   └── page.tsx               # Main Next.js command center layout page
├── components/
│   ├── ThreatCanvas.tsx       # 3D force-directed WebGL graph component
│   ├── EventFeed.tsx          # Real-time telemetry feed component
│   ├── RiskGauge.tsx          # Radial SVG risk index gauge component
│   └── Drilldown.tsx          # Inspection modal drawer & /decide resolution buttons
├── lib/
│   ├── colors.ts              # Single source of truth color mapping for verdicts & node types
│   ├── graphReducer.ts        # Client-side graph state reducer
│   └── ws.ts                  # Reconnecting WebSocket client
├── types/
│   └── events.ts              # TypeScript interface definitions matching backend Pydantic schemas
└── out/                       # Compiled static export assets
```

---

## 3. Detailed Component Breakdown

### A. WebSocket Transport (`dashboard/lib/ws.ts`)
- Manages connection lifecycle to `ws://localhost:8000/ws`.
- Tracks `lastSeq`. On reconnect, automatically appends `?since=${lastSeq}` query parameter to request missed events.
- Emits real-time connection status (`connecting`, `connected`, `disconnected`, `error`).

### B. Graph State Reducer (`dashboard/lib/graphReducer.ts`)
- Folds `GraphSnapshot` and individual `AgentEvent`s into 3D nodes (`GraphNode`) and links (`GraphLink`).
- Nodes:
  - **Agent Node**: `id = agent_id` (`node_type = "agent"`)
  - **Action Node**: `id = event_id` (`node_type = "action"`, scaled by `risk_score`)
  - **Resource Node**: `id = res_<target_resource>` (`node_type = "resource"`)
- Links:
  - Connects `parent_id` -> `event_id` (or `agent_id` -> `event_id`).
  - Connects `event_id` -> `resource_id`.

### C. 3D Threat Canvas (`dashboard/components/ThreatCanvas.tsx`)
- WebGL force-directed graph dynamically imported (SSR disabled).
- Node Geometries:
  - **Agent**: Glowing wireframe icosahedron with inner purple sphere.
  - **Action**: Translucent sphere scaled by risk score (`radius = 4.5 + risk_score * 0.07`).
    - **Quarantined**: Amber outer ring geometry.
    - **Blocked**: Red icosahedron "shield" frame around the node.
  - **Resource**: Cyan box geometry.
- Links: Directional particle beams indicating real-time event telemetry flow.
- Physics: Configured with `cooldownTicks={100}` and `cooldownTime={3000}` so graph physics settles smoothly.

### D. Interactive Drilldown & Decision Drawer (`dashboard/components/Drilldown.tsx`)
- Triggered on selecting any event or 3D graph node.
- Renders:
  - `parent_id` call stack lineage traceback (`#1 agent-01 -> #2 tool:read_file -> #3 $ curl ...`).
  - Command execution payload & target resource.
  - Detailed blast radius score (file count, directory count, network call, system command).
  - YAML policy rules triggered & rationale.
- **Quarantined Decision Buttons**:
  - When an event is `quarantined`, provides **Approve Action** and **Block Action** buttons.
  - Sends HTTP `POST` request to `http://localhost:8000/decide` with `{ event_id, verdict, note }` to resolve the backend pending `asyncio.Future`.

---

## 4. How to Build & Verify

### Step 1: Install & Build Next.js Dashboard
Inside `dashboard/`:
```bash
cd dashboard
npm install
npm run build
```
*Expected Output*: Next.js compiles all pages and outputs static assets to `dashboard/out`.

### Step 2: Launch FastAPI Server
From repository root:
```bash
.venv\Scripts\uvicorn.exe core.agentsentrix.server.app:app --host 0.0.0.0 --port 8000
```
*Expected Output*: Server starts and mounts static assets from `dashboard/out`.

### Step 3: Run Multi-Agent Simulation
In a separate terminal:
```bash
.venv\Scripts\python.exe -m sim.runner
```

### Step 4: Access Dashboard UI
Open your browser and navigate to:
- `http://localhost:8000/` (FastAPI hosted dashboard)
- Or run `npm run dev` in `dashboard/` and open `http://localhost:3000/`

You will see:
1. Real-time 3D node and particle beam updates as simulation agents run.
2. Composite risk gauge updating dynamically.
3. Telemetry log feed populating with `ALLOWED`, `QUARANTINED`, and `BLOCKED` events.
4. Clicking any quarantined node opens the drilldown panel allowing manual **Approve** / **Deny** decisions!

---

## 5. Verification Checklist

- [x] TypeScript contracts defined in `dashboard/types/events.ts`.
- [x] Single source of truth color mappings in `dashboard/lib/colors.ts`.
- [x] State reducer (`graphReducer.ts`) tested with snapshots and event streams.
- [x] Reconnecting WebSocket client (`ws.ts`) verified with `?since=<seq>`.
- [x] 3D Threat Canvas rendered with Three.js primitives and particle beams.
- [x] Drilldown context inspector verified with `POST /decide` approval buttons.
- [x] Next.js build compilation (`npx next build`) passed with **0 errors**.
- [x] Core pytest test suite verified (31/31 passed).
