import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
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
from ..sensors.replay import ReplaySensor
from .ws import ConnectionManager
from .routes import router as api_router
from .static import mount_static_files

logger = logging.getLogger("agentsentrix.server.app")

def create_app(replay_file: Optional[str] = None, speed: float = 1.0) -> FastAPI:
    """FastAPI application factory supporting live and offline replay modes."""

    @asynccontextmanager
    async def lifespan(app_inst: FastAPI) -> AsyncGenerator[None, None]:
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

        # 6. Optional Replay Sensor for Offline Replay Mode
        replay_sensor: Optional[ReplaySensor] = None
        if replay_file and os.path.exists(replay_file):
            logger.info(f"[REPLAY MODE] Attaching ReplaySensor for file '{replay_file}' at speed x{speed}")
            replay_sensor = ReplaySensor(jsonl_path=replay_file, bus=bus, speed_factor=speed)
            await replay_sensor.start()

        # 7. Store instances in app.state for route dependency access
        app_inst.state.bus = bus
        app_inst.state.cache = cache
        app_inst.state.duckdb_sink = duckdb_sink
        app_inst.state.jsonl_sink = jsonl_sink
        app_inst.state.evaluator = evaluator
        app_inst.state.quarantine_mgr = quarantine_mgr
        app_inst.state.mcp_proxy = mcp_proxy
        app_inst.state.projection = projection
        app_inst.state.ws_manager = ws_manager
        app_inst.state.replay_sensor = replay_sensor

        logger.info("AgentSentrix Server pipeline successfully initialized & ready.")
        yield

        # Shutdown Teardown
        logger.info("Shutting down AgentSentrix Server pipeline...")
        if replay_sensor:
            await replay_sensor.stop()
        duckdb_sink.close()
        logger.info("AgentSentrix Server teardown complete.")

    app_inst = FastAPI(
        title="AgentSentrix API Gateway & Real-Time Security Engine",
        description="Inline Interceptor, Multi-Tier Risk Evaluation & 3D Threat Graph Gateway",
        version="1.0.0",
        lifespan=lifespan
    )

    # Allow CORS for Next.js dashboard development
    app_inst.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount REST routes & static assets
    app_inst.include_router(api_router)
    mount_static_files(app_inst)

    return app_inst

app = create_app()
