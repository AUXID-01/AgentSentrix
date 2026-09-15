# AgentSentrix — Stage 8 Security Analytics & MLflow Observability Guide

## 1. Overview
Stage 8 adds **Big-Data Security Analytics & ML Observability** to AgentSentrix without introducing cloud dependencies or impacting real-time security interception performance.

### Key Capabilities:
- **MLflow Observability Tracker**: Logs every risk assessment, tier breakdown scores ($T0, T1, T2$), execution latency ($ms$), and operator false-positive decisions ($POST /decide$).
- **DuckDB Parquet Data Exporter**: Exports real-time event telemetry into industry-standard `.parquet` binary datasets for offline PySpark analytics.
- **Local PySpark / Pandas Analytics Script**: Computes offline risk scores by agent persona and verdict distribution metrics.
- **Databricks PySpark Notebook**: Ready-to-upload PySpark notebook (`analytics/databricks_notebook.py`) for enterprise data teams and presentation demos.

---

## 2. MLflow Experiment Tracking

MLflow runs 100% locally by default storing experiment data under `./mlruns`.

### Starting the Local MLflow UI:
```bash
# Launch MLflow tracking server on http://localhost:5000
.venv\Scripts\mlflow.exe ui --port 5000
```
Open `http://localhost:5000` in your web browser to view the **AgentSentrix_Risk_Evaluations** experiment dashboard.

### Tracked Metrics & Parameters:
| Metric / Tag | Type | Description |
|---|---|---|
| `t0_rules_score` | Metric | Deterministic YAML rule risk score |
| `t1_local_score` | Metric | Local Ollama prompt injection score |
| `t2_llm_score` | Metric | Groq structured LLM-as-a-judge score |
| `final_risk_score` | Metric | Composite final calculated risk score |
| `latency_ms` | Metric | End-to-end evaluation latency in milliseconds |
| `is_false_positive` | Metric | `1.0` if operator approved a quarantined action, `0.0` otherwise |
| `agent_id` | Tag | Persona ID (`refactorer-01`, `rogue-01`, etc.) |
| `verdict` | Tag | Security decision (`allowed`, `quarantined`, `blocked`) |

---

## 3. DuckDB Parquet Data Export & PySpark Analytics

AgentSentrix telemetry captured in embedded DuckDB (`data/agentsentrix.duckdb`) is exported using high-speed zero-copy zero-dependency Parquet format.

### Running Offline Security Analytics:
```bash
.venv\Scripts\python.exe -m analytics.pyspark_analytics
```

#### Sample Output:
```text
================ AGENTSENTRIX PARQUET SECURITY ANALYTICS ================
Parquet Dataset    : C:\agent_sentrix\AgentSentrix\data\exports\session_analytics.parquet
Total Telemetry    : 8 events processed

─── RISK BY AGENT PERSONA ───────────────────────────────────────────────
  • refactorer-01        | Actions:  2 | Avg Risk:  15.0/100 | Max:  15
  • test-runner-01       | Actions:  2 | Avg Risk:  10.0/100 | Max:  10
  • mcp-installer-01     | Actions:  1 | Avg Risk:  50.0/100 | Max:  50
  • rogue-01             | Actions:  3 | Avg Risk:  93.3/100 | Max: 100

─── VERDICT DISTRIBUTION SUMMARY ───────────────────────────────────────
  • ALLOWED          :  3 events ( 37.5%)
  • QUARANTINED      :  1 events ( 12.5%)
  • BLOCKED          :  4 events ( 50.0%)
========================================================================
```

---

## 4. Databricks PySpark Integration

To upload and run analytics in **Databricks Community Edition** (or any PySpark cluster):

1. Run the local simulation to generate Parquet telemetry:
   ```bash
   .venv\Scripts\python.exe -m sim.runner
   .venv\Scripts\python.exe -m analytics.pyspark_analytics
   ```
2. Download or copy `data/exports/session_analytics.parquet`.
3. In Databricks Workspace, navigate to **Data** $\rightarrow$ **Add Data** $\rightarrow$ **Create or Upload Table** and upload `session_analytics.parquet` into `/FileStore/tables/session_analytics.parquet`.
4. Import `analytics/databricks_notebook.py` as a new Python notebook.
5. Execute cells to generate risk-by-agent heatmaps and verdict charts for your demo presentation.

---

## 5. Verification & Testing

Run the automated test suite to verify Stage 8 functionality:
```bash
.venv\Scripts\pytest.exe tests/test_stage8.py -v
```
