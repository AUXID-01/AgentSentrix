import os
import logging
import duckdb
from typing import Optional

logger = logging.getLogger("agentsentrix.analytics.exporter")

class ParquetExporter:
    """
    Exports session telemetry from embedded DuckDB analytical database
    into standard Parquet (.parquet) files for PySpark & Databricks analytics.
    """

    def __init__(self, db_path: str = "data/agentsentrix.duckdb", output_dir: str = "data/exports") -> None:
        self.db_path = db_path
        self.output_dir = output_dir

    def export_to_parquet(self, session_id: Optional[str] = None, output_file: Optional[str] = None) -> str:
        """Export events table to a Parquet binary dataset."""
        os.makedirs(self.output_dir, exist_ok=True)
        
        target_filename = output_file or (
            f"session_{session_id}.parquet" if session_id else "session_analytics.parquet"
        )
        target_path = os.path.join(self.output_dir, target_filename)
        abs_target_path = os.path.abspath(target_path)

        # Connect to DuckDB database file or fallback
        con = None
        try:
            con = duckdb.connect(self.db_path, read_only=True)
        except Exception:
            con = duckdb.connect(":memory:")
            # Create schema if database not available
            con.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id VARCHAR, seq BIGINT, ts TIMESTAMP, session_id VARCHAR,
                    sensor VARCHAR, agent_id VARCHAR, action_type VARCHAR,
                    verdict VARCHAR, risk_score INTEGER, raw_payload VARCHAR, payload_json JSON
                )
            """)

        clean_path = abs_target_path.replace("\\", "/")
        try:
            if session_id:
                query = f"COPY (SELECT * FROM events WHERE session_id = '{session_id}') TO '{clean_path}' (FORMAT PARQUET);"
            else:
                query = f"COPY (SELECT * FROM events) TO '{clean_path}' (FORMAT PARQUET);"

            con.execute(query)
            logger.info(f"[ParquetExporter] Successfully exported telemetry events to Parquet: {abs_target_path}")
            return abs_target_path
        finally:
            if con:
                con.close()
