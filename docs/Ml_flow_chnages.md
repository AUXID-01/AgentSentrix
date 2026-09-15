# AgentSentrix — Changes & Additions Since Last Git Commit (`37a0cbe`)

## 1. Summary of Changes
This document details all new files, core engine modifications, analytics pipelines, documentation, and test additions introduced after commit `37a0cbe` (**Stage 8 Implementation & Developer SDK Documentation**).

---

## 2. New Files Created

### A. Analytics & ML Observability Module (`core/agentsentrix/analytics/`)
- **[`core/agentsentrix/analytics/__init__.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/analytics/__init__.py)**: Export package interface for `MLflowTracker` and `ParquetExporter`.
- **[`core/agentsentrix/analytics/mlflow_tracker.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/analytics/mlflow_tracker.py)**:
  - Connects to MLflow (`sqlite:///mlflow.db` default).
  - Logs assessment metrics (`t0_rules_score`, `t1_local_score`, `t2_llm_score`, `final_risk_score`, `latency_ms`).
  - Logs event metadata (`agent_id`, `action_type`, `target_label`, `verdict`).
  - Logs operator false-positive override signals (`is_false_positive`) when human decisions are submitted via `/decide`.
- **[`core/agentsentrix/analytics/exporter.py`](file:///c:/agent_sentrix/AgentSentrix/core/agentsentrix/analytics/exporter.py)**:
  - High-performance DuckDB SQL exporter converting embedded telemetry into standard binary `.parquet` datasets (`data/exports/session_analytics.parquet`).

### B. Big-Data & PySpark Analytics (`analytics/`)
- **[`analytics/pyspark_analytics.py`](file:///c:/agent_sentrix/AgentSentrix/analytics/pyspark_analytics.py)**:
  - Command-line offline analytics script executing Parquet export, risk score aggregation by agent persona, and verdict distribution breakdowns.
- **[`analytics/databricks_notebook.py`](file:///c:/agent_sentrix/AgentSentrix/analytics/databricks_notebook.py)**:
  - Ready-to-upload PySpark notebook artifact for Databricks Community Edition for generating presentation heatmaps and false-positive charts.

### C. Developer Documentation & Guides (`docs/`)
- **[`docs/STAGE8_ANALYTICS_AND_MLFLOW_GUIDE.md`](file:///c:/agent_sentrix/AgentSentrix/docs/STAGE8_ANALYTICS_AND_MLFLOW_GUIDE.md)**:
  - Architecture and operational guide for MLflow tracking, local UI server execution, and Parquet data pipelines.
- **[`docs/DEVELOPER_SDK_AND_INTEGRATION_GUIDE.md`](file:///c:/agent_sentrix/AgentSentrix/docs/DEVELOPER_SDK_AND_INTEGRATION_GUIDE.md)**:
  - Complete SDK integration guide explaining how developers install `agentsentrix`, connect agents via MCP or SDK middleware, and handle quarantine interception.
- **[`docs/CHANGES_SINCE_LAST_COMMIT.md`](file:///c:/agent_sentrix/AgentSentrix/docs/CHANGES_SINCE_LAST_COMMIT.md)**:
  - This summary file documenting all changes.

### D. Automated Test Suite (`tests/`)
- **[`tests/test_stage8.py`](file:///c:/agent_sentrix/AgentSentrix/tests/test_stage8.py)**:
  - Unit tests covering MLflow tracker initialization, assessment logging, human override signals, DuckDB Parquet exporting, and PySpark analytics execution (38/38 suite tests passing).

---

## 3. Modified Files

### A. Multi-Tier Risk Engine (`core/agentsentrix/engine/evaluator.py`)
- **Initialized MLflow Tracker**: Added `MLflowTracker` instantiation in `MultiTierEvaluator.__init__`.
- **Fast-Path Logging**: Added `mlflow_tracker.log_assessment(event, assessment)` inside Tier 0 fast-path exit.
- **Composite Decision Logging**: Added `mlflow_tracker.log_assessment(event, assessment)` inside composite decision exit.

### B. Server REST API (`core/agentsentrix/server/routes.py`)
- **Human Override Signal**: Updated `POST /decide` endpoint to invoke `mlflow_tracker.log_human_override(...)` whenever an operator approves or blocks a quarantined action.

### C. Git Configuration (`.gitignore`)
- Added `mlruns/`, `.mlruns/`, and `data/exports/` to prevent local MLflow run metadata files and temporary Parquet exports from dirtying Git status.

---

## 4. Verification & Test Status
- Total automated unit tests: **38 / 38 PASSED**
- All tools and simulation scenarios verified cleanly.
