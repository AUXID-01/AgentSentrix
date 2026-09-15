import os
import duckdb
from typing import Any
from ...schema.events import AgentEvent

class DuckDBSink:
    """DuckDB persistence sink writing AgentEvents to an embedded database."""

    def __init__(self, db_path: str = "data/agentsentrix.duckdb") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        try:
            self.con = duckdb.connect(self.db_path)
        except Exception as exc:
            import warnings
            warnings.warn(
                f"[DuckDBSink] Unable to lock DuckDB database file '{db_path}' ({exc}). "
                f"Falling back to an in-memory instance (:memory:) to prevent process crash.",
                UserWarning,
                stacklevel=2
            )
            self.con = duckdb.connect(":memory:")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize events table schema."""
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
        """Persist an incoming AgentEvent into DuckDB."""
        sensor_str = event.sensor.value if hasattr(event.sensor, "value") else str(event.sensor)
        action_str = event.action_type.value if hasattr(event.action_type, "value") else str(event.action_type)
        verdict_str = event.risk.verdict.value if hasattr(event.risk.verdict, "value") else str(event.risk.verdict)
        ts_val = event.ts.isoformat() if hasattr(event.ts, "isoformat") else str(event.ts)
        payload_json = event.model_dump_json()

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

    def close(self) -> None:
        """Close connection to DuckDB."""
        if hasattr(self, "con") and self.con:
            self.con.close()
