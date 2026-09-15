import os
import tempfile
import pytest
import duckdb
import pandas as pd

from core.agentsentrix.analytics.mlflow_tracker import MLflowTracker
from core.agentsentrix.analytics.exporter import ParquetExporter
from core.agentsentrix.schema.enums import Verdict, ActionType, Sensor, NodeKind
from core.agentsentrix.schema.events import AgentEvent, RiskAssessment, TierScores, AgentRef, Target
from analytics.pyspark_analytics import run_analytics

def test_mlflow_tracker_initialization():
    tracker = MLflowTracker(experiment_name="Test_Experiment")
    assert tracker.experiment_name == "Test_Experiment"
    assert tracker.enabled is True

def test_mlflow_tracker_log_assessment():
    tracker = MLflowTracker(experiment_name="Test_Assessment_Log")
    event = AgentEvent(
        id="evt_test_1",
        session_id="test_session_mlflow",
        agent=AgentRef(id="test-agent", name="Test Agent", task="Testing MLflow"),
        sensor=Sensor.SHELL_SHIM,
        action_type=ActionType.FILE_READ,
        target=Target(kind=NodeKind.FILE, label="Test File", path="/tmp/test.txt"),
        raw_payload="cat /tmp/test.txt",
        risk=RiskAssessment(
            score=15,
            verdict=Verdict.ALLOWED,
            tier_scores=TierScores(t0_rules=15),
            engine="TestEngine",
            rationale="Safe read"
        )
    )
    assessment = event.risk
    event.latency_ms = 12.5

    run_id = tracker.log_assessment(event, assessment)
    assert run_id is not None
    assert isinstance(run_id, str)

def test_mlflow_tracker_log_human_override():
    tracker = MLflowTracker(experiment_name="Test_Override_Log")
    success = tracker.log_human_override(
        event_id="evt_test_123",
        original_verdict="quarantined",
        new_verdict="allowed",
        note="Approved by security team"
    )
    assert success is True

def test_parquet_exporter():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.duckdb")
        con = duckdb.connect(db_path)
        con.execute("""
            CREATE TABLE events (
                id VARCHAR, seq BIGINT, ts TIMESTAMP, session_id VARCHAR,
                sensor VARCHAR, agent_id VARCHAR, action_type VARCHAR,
                verdict VARCHAR, risk_score INTEGER, raw_payload VARCHAR, payload_json JSON
            )
        """)
        con.execute("""
            INSERT INTO events VALUES (
                'evt_1', 1, CURRENT_TIMESTAMP, 'sess_1',
                'FS_HOOK', 'agent_a', 'FILE_READ', 'allowed', 10, 'payload_1', '{}'
            )
        """)
        con.close()

        exporter = ParquetExporter(db_path=db_path, output_dir=tmp_dir)
        output_file = exporter.export_to_parquet(session_id="sess_1")

        assert os.path.exists(output_file)
        assert output_file.endswith(".parquet")

        df = pd.read_parquet(output_file)
        assert len(df) == 1
        assert df.iloc[0]["agent_id"] == "agent_a"
        assert df.iloc[0]["risk_score"] == 10

def test_pyspark_analytics_runner():
    res = run_analytics()
    assert isinstance(res, dict)
    assert "total_events" in res

def test_databricks_notebook_artifact_exists():
    assert os.path.exists("analytics/databricks_notebook.py"), "Missing analytics/databricks_notebook.py"
    with open("analytics/databricks_notebook.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "SparkSession" in content
    assert "session_analytics.parquet" in content
