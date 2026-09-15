import os
import sys
import logging
import pandas as pd
from core.agentsentrix.analytics.exporter import ParquetExporter

logger = logging.getLogger("agentsentrix.analytics.pyspark")

def run_analytics() -> dict:
    """Run Parquet export & security analytics calculations (PySpark / Pandas mode)."""
    # 1. Export DuckDB data to Parquet
    exporter = ParquetExporter()
    parquet_path = exporter.export_to_parquet()

    if not os.path.exists(parquet_path):
        print(f"No Parquet export found at {parquet_path}")
        return {}

    # 2. Read Parquet Dataset using Pandas / PyArrow
    df = pd.read_parquet(parquet_path)
    
    total_events = len(df)
    if total_events == 0:
        print("\n================ AGENTSENTRIX PARQUET SECURITY ANALYTICS ================")
        print("Dataset Path       : " + parquet_path)
        print("Total Telemetry    : 0 events (Empty dataset)")
        print("========================================================================\n")
        return {"total_events": 0}

    # 3. Aggregate Risk Score by Agent Persona
    risk_by_agent = df.groupby("agent_id")["risk_score"].agg(["mean", "max", "count"]).reset_index()
    risk_by_agent.columns = ["agent_id", "avg_risk", "max_risk", "total_actions"]

    # 4. Verdict Distribution Summary
    verdict_summary = df["verdict"].value_counts().to_dict()

    print("\n================ AGENTSENTRIX PARQUET SECURITY ANALYTICS ================")
    print(f"Parquet Dataset    : {parquet_path}")
    print(f"Total Telemetry    : {total_events} events processed\n")
    print("─── RISK BY AGENT PERSONA ───────────────────────────────────────────────")
    for _, row in risk_by_agent.iterrows():
        print(f"  • {row['agent_id']:<20} | Actions: {row['total_actions']:2d} | Avg Risk: {row['avg_risk']:5.1f}/100 | Max: {row['max_risk']:3d}")

    print("\n─── VERDICT DISTRIBUTION SUMMARY ───────────────────────────────────────")
    for verdict, cnt in verdict_summary.items():
        print(f"  • {str(verdict).upper():<16} : {cnt:2d} events ({(cnt/total_events)*100:5.1f}%)")
    print("========================================================================\n")

    return {
        "total_events": total_events,
        "risk_by_agent": risk_by_agent.to_dict(orient="records"),
        "verdicts": verdict_summary
    }

if __name__ == "__main__":
    run_analytics()
