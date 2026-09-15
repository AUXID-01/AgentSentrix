import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..bus.bus import EventBus
from ..bus.cache import StateCache
from ..bus.sinks.duckdb_sink import DuckDBSink
from ..bus.sinks.jsonl_sink import JSONLSink
from ..engine.evaluator import MultiTierEvaluator
from ..proxy.quarantine import QuarantineManager
from ..proxy.mcp_proxy import MCPProxy
from ..projection.graph_projection import GraphProjection
from .ws import ConnectionManager
from .routes import router as api_router
from .static import mount_static_files

logger = logging.getLogger("agentsentrix.server.app")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager starting sinks, bus workers, and server state on boot."""
    logger.info("Initializing AgentSentrix Server pipeline & dependencies...")

    # 1. Core Services & Storage
    bus = EventBus(maxlen=1000)
    cache = StateCache(host="localhost", port=6379)
    duckdb_sink = DuckDBSink(db_path="data/agentsentrix.duckdb")
    jsonl_sink = JSONLSink(target_dir="data/sessions")

    # 2. Risk Evaluation & Quarantine Manager
    evaluator = MultiTierEvaluator(cache=cache)
    quarantine_mgr = QuarantineManager(cache=cache)

    # 3. Projection & WebSocket ConnectionManager
    projection = GraphProjection()
    ws_manager = ConnectionManager(bus=bus)

    # 4. Inline Proxy
    mcp_proxy = MCPProxy(
        bus=bus,
        evaluator=evaluator,
        quarantine_mgr=quarantine_mgr
    )

    # 5. Bus Subscriptions (Pub/Sub Event Wire)
    bus.subscribe(duckdb_sink)
    bus.subscribe(jsonl_sink)
    bus.subscribe(projection)
    bus.subscribe(ws_manager.on_event)

    # 6. Store instances in app.state for route dependency access
    app.state.bus = bus
    app.state.cache = cache
    app.state.duckdb_sink = duckdb_sink
    app.state.jsonl_sink = jsonl_sink
    app.state.evaluator = evaluator
    app.state.quarantine_mgr = quarantine_mgr
    app.state.mcp_proxy = mcp_proxy
    app.state.projection = projection
    app.state.ws_manager = ws_manager

    logger.info("AgentSentrix Server pipeline successfully initialized & ready.")
    yield

    # Shutdown Teardown
    logger.info("Shutting down AgentSentrix Server pipeline...")
    duckdb_sink.close()
    logger.info("AgentSentrix Server teardown complete.")

def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="AgentSentrix API Gateway & Real-Time Security Engine",
        description="Inline Interceptor, Multi-Tier Risk Evaluation & 3D Threat Graph Gateway",
        version="1.0.0",
        lifespan=lifespan
    )

    # Allow CORS for Next.js dashboard development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount REST routes & static assets
    app.include_router(api_router)
    mount_static_files(app)

    return app

app = create_app()
