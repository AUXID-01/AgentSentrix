# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # AgentSentrix — Big-Data Security Analytics & Eval Benchmarking
# MAGIC 
# MAGIC This PySpark notebook aggregates session telemetry exported from AgentSentrix (`data/exports/session_analytics.parquet`).
# MAGIC Calculates **Risk-by-Agent Persona**, **Verdict Distribution**, and **False Positive Rates**.

# COMMAND ----------
# Cell 1: Load Parquet Telemetry Dataset into PySpark DataFrame
import os
try:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    spark = SparkSession.builder.appName("AgentSentrixSecurityAnalytics").getOrCreate()
    parquet_path = "/FileStore/tables/session_analytics.parquet"

    # Fallback to local path if running outside Databricks cluster
    if not os.path.exists(parquet_path) and os.path.exists("data/exports/session_analytics.parquet"):
        parquet_path = "data/exports/session_analytics.parquet"

    print(f"Loading AgentSentrix Parquet Dataset from: {parquet_path}")
    df = spark.read.parquet(parquet_path)
    df.printSchema()
except Exception as e:
    print(f"Databricks PySpark initialization note: {e}")

# COMMAND ----------
# Cell 2: Aggregate Average Risk Score by Agent Persona
# COMMAND ----------
"""
# Databricks display visualization
risk_by_agent = df.groupBy("agent_id").agg(
    F.avg("risk_score").alias("avg_risk_score"),
    F.max("risk_score").alias("max_risk_score"),
    F.count("id").alias("total_actions")
)
display(risk_by_agent)
"""

# COMMAND ----------
# Cell 3: Verdict Distribution Breakdown (Allowed, Quarantined, Blocked)
# COMMAND ----------
"""
verdict_summary = df.groupBy("verdict").count().withColumnRenamed("count", "total_events")
display(verdict_summary)
"""

# COMMAND ----------
# Cell 4: Calculate False-Positive Signal (Quarantined Actions Approved by Human Operator)
# COMMAND ----------
"""
quarantine_events = df.filter(F.col("verdict") == "quarantined")
human_approvals = df.filter((F.col("verdict") == "quarantined") & (F.col("raw_payload").contains("operator")))

fp_rate = (human_approvals.count() / max(quarantine_events.count(), 1)) * 100
print(f"AgentSentrix Quarantine False-Positive Rate: {fp_rate:.2f}%")
"""
