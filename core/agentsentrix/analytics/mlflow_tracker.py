import os
import logging
import warnings
from typing import Optional, Any
from ..schema.events import AgentEvent, RiskAssessment

logger = logging.getLogger("agentsentrix.analytics.mlflow")

class MLflowTracker:
    """
    ML Observability & Risk Evaluation Tracker for AgentSentrix.
    - Logs parameters: agent_id, action_type, target_resource, session_id.
    - Logs metrics: t0_score, t1_score, t2_score, final_score, latency_ms.
    - Logs human overrides (false positives) when operator decides via POST /decide.
    """

    def __init__(self, experiment_name: str = "AgentSentrix_Risk_Evaluations", tracking_uri: Optional[str] = None) -> None:
        self.experiment_name = experiment_name
        self.tracking_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
        self.enabled = False

        try:
            os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
            import mlflow
            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.experiment_name)
            self.enabled = True
            logger.info(f"[MLflow] Active tracking experiment '{self.experiment_name}' at {self.tracking_uri}")
        except Exception as exc:
            warnings.warn(
                f"[MLflowTracker] MLflow initialization failed ({exc}). Analytics logging will be bypassed.",
                UserWarning,
                stacklevel=2
            )
            self.enabled = False

    def log_assessment(self, event: AgentEvent, assessment: RiskAssessment) -> Optional[str]:
        """Log a risk engine assessment run to MLflow."""
        if not self.enabled:
            return None

        try:
            import mlflow
            with mlflow.start_run(run_name=f"eval_{event.id[:8]}", nested=True) as run:
                # Log Tags & Parameters
                mlflow.set_tag("session_id", event.session_id)
                mlflow.set_tag("agent_id", event.agent.id)
                mlflow.set_tag("verdict", assessment.verdict.value)
                
                mlflow.log_param("event_id", event.id)
                mlflow.log_param("action_type", event.action_type.value if hasattr(event.action_type, "value") else str(event.action_type))
                mlflow.log_param("target_label", event.target.label if hasattr(event.target, "label") else str(event.target))
                mlflow.log_param("sensor", event.sensor.value if hasattr(event.sensor, "value") else str(event.sensor))

                # Log Metrics
                t0_score = assessment.tier_scores.t0_rules if assessment.tier_scores else 0
                t1_score = assessment.tier_scores.t1_local if assessment.tier_scores and assessment.tier_scores.t1_local is not None else 0
                t2_score = assessment.tier_scores.t2_llm if assessment.tier_scores and assessment.tier_scores.t2_llm is not None else 0

                mlflow.log_metric("t0_rules_score", t0_score)
                mlflow.log_metric("t1_local_score", t1_score)
                mlflow.log_metric("t2_llm_score", t2_score)
                mlflow.log_metric("final_risk_score", assessment.score)
                mlflow.log_metric("latency_ms", event.latency_ms or 0.0)

                run_id = run.info.run_id
                logger.info(f"[MLflow] Logged assessment run '{run_id}' for event '{event.id}' -> Score: {assessment.score}")
                return run_id
        except Exception as exc:
            logger.warning(f"[MLflow] Failed to log assessment: {exc}")
            return None

    def log_human_override(self, event_id: str, original_verdict: str, new_verdict: str, note: Optional[str] = None) -> bool:
        """Log operator human quarantine decision override to MLflow as a false-positive / eval signal."""
        if not self.enabled:
            return False

        try:
            import mlflow
            with mlflow.start_run(run_name=f"decide_{event_id[:8]}", nested=True) as run:
                mlflow.set_tag("override_type", "human_decision")
                mlflow.log_param("event_id", event_id)
                mlflow.log_param("original_verdict", original_verdict)
                mlflow.log_param("new_verdict", new_verdict)
                mlflow.log_param("note", note or "")

                is_false_positive = 1.0 if original_verdict.lower() == "quarantined" and new_verdict.lower() == "allowed" else 0.0
                mlflow.log_metric("is_false_positive", is_false_positive)

                logger.info(f"[MLflow] Logged human override for '{event_id}' -> FalsePositive: {is_false_positive}")
                return True
        except Exception as exc:
            logger.warning(f"[MLflow] Failed to log human override: {exc}")
            return False
