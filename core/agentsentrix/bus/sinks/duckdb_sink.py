import os
import duckdb
import asyncio
import threading
import warnings
import logging
from typing import Any
from ...schema.events import AgentEvent

logger = logging.getLogger("agentsentrix.sinks.duckdb")

class DuckDBSink:
    """
    DuckDB persistence sink writing AgentEvents to an embedded database.
    Includes thread and asyncio lock serialization to prevent file lock contention,
    plus automatic fallback to in-memory mode under concurrent process locks.
    """

    def __init__(self, db_path: str = "data/agentsentrix.duckdb") -> None:
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._thread_lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        try:
            self.con = duckdb.connect(self.db_path)
        except Exception as exc:
            warnings.warn(
                f"[DuckDBSink] Unable to lock DuckDB database file '{db_path}' ({exc}). "
                f"Falling back to an in-memory instance (:memory:) to prevent process crash.",
                UserWarning,
                stacklevel=2
            )
            self.con = duckdb.connect(":memory:")

        self._init_db()

    def _init_db(self) -> None:
        """Initialize events table schema and PRAGMAs."""
        with self._thread_lock:
            try:
                self.con.execute("PRAGMA threads=4;")
            except Exception:
                pass
            self.con.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id VARCHAR PRIMARY KEY,
                    seq BIGINT,
                    ts TIMESTAMP,
                    session_id VARCHAR,
                    sensor VARCHAR,
                    agent_id VARCHAR,
                    action_type VARCHAR,
                    verdict VARCHAR,
                    risk_score INTEGER,
                    raw_payload VARCHAR,
                    payload_json JSON
                );
            """)

    async def consume(self, event: AgentEvent) -> None:
        """Persist an incoming AgentEvent into DuckDB under lock protection."""
        async with self._lock:
            self._write_event_sync(event)

    def _write_event_sync(self, event: AgentEvent) -> None:
        sensor_str = event.sensor.value if hasattr(event.sensor, "value") else str(event.sensor)
        action_str = event.action_type.value if hasattr(event.action_type, "value") else str(event.action_type)
        verdict_str = event.risk.verdict.value if hasattr(event.risk.verdict, "value") else str(event.risk.verdict)
        ts_val = event.ts.isoformat() if hasattr(event.ts, "isoformat") else str(event.ts)
        payload_json = event.model_dump_json()

        with self._thread_lock:
            try:
                self.con.execute(
                    """
                    INSERT OR REPLACE INTO events (
                        id, seq, ts, session_id, sensor, agent_id, action_type, verdict, risk_score, raw_payload, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        event.id,
                        event.seq,
                        ts_val,
                        event.session_id,
                        sensor_str,
                        event.agent.id,
                        action_str,
                        verdict_str,
                        event.risk.score,
                        event.raw_payload,
                        payload_json
                    ]
                )
            except Exception as exc:
                logger.warning(f"[DuckDBSink] File write collision/error: {exc}. Switching to in-memory fallback.")
                try:
                    self.con = duckdb.connect(":memory:")
                    self._init_db()
                    self.con.execute(
                        """
                        INSERT OR REPLACE INTO events (
                            id, seq, ts, session_id, sensor, agent_id, action_type, verdict, risk_score, raw_payload, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            event.id,
                            event.seq,
                            ts_val,
                            event.session_id,
                            sensor_str,
                            event.agent.id,
                            action_str,
                            verdict_str,
                            event.risk.score,
                            event.raw_payload,
                            payload_json
                        ]
                    )
                except Exception as fatal_err:
                    logger.error(f"[DuckDBSink] Fatal error persisting event {event.id}: {fatal_err}")

    def close(self) -> None:
        """Close connection to DuckDB."""
        with self._thread_lock:
            if hasattr(self, "con") and self.con:
                try:
                    self.con.close()
                except Exception:
                    pass
