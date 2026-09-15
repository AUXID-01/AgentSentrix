import os
import hashlib
import time
import json
import logging
import warnings
from typing import Optional
import httpx

from .base import RiskEngine
from .blast_radius import BlastRadiusCalculator
from ..policy.loader import PolicyLoader
from ..bus.cache import StateCache
from ..schema.enums import Verdict, ActionType
from ..schema.events import AgentEvent, RiskAssessment, BlastRadius, TierScores

logger = logging.getLogger("agentsentrix.evaluator")

class MultiTierEvaluator(RiskEngine):
    """
    Production Multi-Tier Risk Engine for AgentSentrix.
    - Tier 0 (~1ms): Deterministic YAML rules & Shannon entropy secrets detection.
    - Tier 1 (~50ms): Local Ollama prompt-injection & intent-drift classifier.
    - Tier 2 (~300ms): Groq structured LLM-as-a-judge for ambiguous scores (30-70).
    - Caching: Redis state cache by normalized action hash.
    - Resilience: Zero unhandled crashes; explicit warnings on service unreachability.
    """

    def __init__(
        self,
        policy_loader: Optional[PolicyLoader] = None,
        cache: Optional[StateCache] = None,
        ollama_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        groq_api_key: Optional[str] = None
    ) -> None:
        self.policy_loader = policy_loader or PolicyLoader()
        self.cache = cache or StateCache()
        self.blast_calculator = BlastRadiusCalculator()
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "llama3.2:latest")
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        try:
            from ..analytics.mlflow_tracker import MLflowTracker
            self.mlflow_tracker = MLflowTracker()
        except Exception:
            self.mlflow_tracker = None

    def compute_action_hash(self, event: AgentEvent) -> str:
        """Compute SHA256 hash of normalized action payload for caching."""
        target_str = event.target.path or event.target.host or event.target.label or ""
        raw_str = event.raw_payload or ""
        action_str = event.action_type.value if hasattr(event.action_type, "value") else str(event.action_type)
        content = f"{action_str}:{target_str}:{raw_str}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def assess(self, event: AgentEvent) -> tuple[RiskAssessment, BlastRadius]:
        start_time = time.perf_counter()

        # Compute Blast Radius metrics first
        blast_radius = self.blast_calculator.compute(event)

        # Check Cache
        action_hash = self.compute_action_hash(event)
        cached_verdict = self.cache.get_verdict(action_hash)
        if cached_verdict:
            cached_verdict.cached = True
            event.latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return cached_verdict, blast_radius

        # -------------------------------------------------------------
        # Tier 0 Evaluation (~1ms)
        # -------------------------------------------------------------
        t0_result = self.policy_loader.evaluate(event)
        t0_score = t0_result.max_score if t0_result.matched else 0
        logger.info(f"[EVALUATOR] [TIER 0] Rule Match: {t0_result.matched} | Score: {t0_score} | Rules: {t0_result.matched_rule_ids}")

        # Fast path exit for high confidence Tier 0 hits (score >= 75 or explicit low risk safe read <= 20)
        if t0_result.matched and (t0_score >= 75 or t0_score <= 20):
            verdict = t0_result.verdict
            assessment = RiskAssessment(
                score=t0_score,
                verdict=verdict,
                tier_scores=TierScores(t0_rules=t0_score),
                policy_ids=t0_result.matched_rule_ids,
                rationale=t0_result.rationale,
                engine="MultiTierEvaluator-Tier0",
                cached=False
            )
            self.cache.set_verdict(action_hash, assessment)
            event.latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if self.mlflow_tracker:
                self.mlflow_tracker.log_assessment(event, assessment)
            logger.info(f"[EVALUATOR] [FAST-PATH EXIT] Tier 0 -> Score: {t0_score} | Verdict: {verdict.value} | Latency: {event.latency_ms}ms")
            return assessment, blast_radius

        # -------------------------------------------------------------
        # Tier 1 Evaluation (~50ms) - Local Ollama
        # -------------------------------------------------------------
        t1_score = await self._eval_tier1_ollama(event)
        logger.info(f"[EVALUATOR] [TIER 1] Local Ollama ({self.ollama_model}) -> Score: {t1_score}")

        # Combine Tier 0 and Tier 1 scores
        combined_score = max(t0_score, t1_score if t1_score is not None else 0)

        # -------------------------------------------------------------
        # Tier 2 Evaluation (~300ms) - Groq LLM-as-Judge
        # Only fires if combined score lands in the ambiguous band (30-70)
        # -------------------------------------------------------------
        t2_score: Optional[int] = None
        t2_rationale: Optional[str] = None
        if 30 <= combined_score <= 70:
            logger.info(f"[EVALUATOR] [TIER 2 TRIGGERED] Score {combined_score} in ambiguous band (30-70). Invoking Groq LLM-as-a-Judge...")
            t2_res = await self._eval_tier2_groq(event, combined_score)
            if t2_res:
                t2_score, t2_rationale = t2_res
                logger.info(f"[EVALUATOR] [TIER 2 RESULT] Groq Score: {t2_score} | Rationale: {t2_rationale}")

        # Calculate final composite score
        scores = [t0_score]
        if t1_score is not None:
            scores.append(t1_score)
        if t2_score is not None:
            scores.append(t2_score)

        final_score = max(scores)

        # Determine verdict based on threshold mapping
        if final_score >= 75:
            final_verdict = Verdict.BLOCKED
        elif final_score >= 40:
            final_verdict = Verdict.QUARANTINED
        else:
            final_verdict = Verdict.ALLOWED

        rationales = []
        if t0_result.rationale:
            rationales.append(t0_result.rationale)
        if t1_score is not None and t1_score > 30:
            rationales.append(f"Tier 1 (Ollama) elevated score to {t1_score}")
        if t2_rationale:
            rationales.append(f"Tier 2 (Groq): {t2_rationale}")

        if not rationales:
            rationales.append("No security policy violations detected.")

        assessment = RiskAssessment(
            score=final_score,
            verdict=final_verdict,
            tier_scores=TierScores(t0_rules=t0_score, t1_local=t1_score, t2_llm=t2_score),
            policy_ids=t0_result.matched_rule_ids,
            rationale=" | ".join(rationales),
            engine="MultiTierEvaluator",
            cached=False
        )

        # Cache the result
        self.cache.set_verdict(action_hash, assessment)
        event.latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if self.mlflow_tracker:
            self.mlflow_tracker.log_assessment(event, assessment)
        logger.info(f"[EVALUATOR] [COMPOSITE DECISION] Event '{event.id}' -> Score: {final_score}/100 | Verdict: {final_verdict.value} | Latency: {event.latency_ms}ms")
        return assessment, blast_radius

    async def _eval_tier1_ollama(self, event: AgentEvent) -> Optional[int]:
        """Call local Ollama endpoint for prompt injection and intent drift evaluation."""
        payload = {
            "model": self.ollama_model,
            "prompt": (
                f"Task: {event.task_context or event.agent.task or 'N/A'}\n"
                f"Action: {event.action_type.value}\n"
                f"Target: {event.target.label}\n"
                f"Payload: {event.raw_payload}\n"
                "Evaluate risk score (0 to 100) for prompt injection or intent drift. "
                "Respond ONLY with a JSON object: {\"score\": int, \"reason\": string}"
            ),
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.post(f"{self.ollama_url}/api/generate", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    response_text = data.get("response", "")
                    json_match = json.loads(response_text[response_text.find("{"):response_text.rfind("}")+1])
                    return int(json_match.get("score", 0))
        except Exception as exc:
            warnings.warn(
                f"Ollama local endpoint ({self.ollama_url}) unavailable: {exc}. Tier 1 evaluation bypassed.",
                category=UserWarning,
                stacklevel=2
            )
            logger.warning(f"Ollama local endpoint unavailable: {exc}")
            return None
        return None

    async def _eval_tier2_groq(self, event: AgentEvent, current_score: int) -> Optional[tuple[int, str]]:
        """Call Groq API for LLM-as-a-judge evaluation when score is in the ambiguous band."""
        if not self.groq_api_key:
            warnings.warn(
                "Groq API key missing (GROQ_API_KEY). Tier 2 evaluation bypassed.",
                category=UserWarning,
                stacklevel=2
            )
            return None

        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        prompt_content = (
            f"Analyze this security event:\n"
            f"Agent: {event.agent.name}\n"
            f"Task Context: {event.task_context or 'N/A'}\n"
            f"Action: {event.action_type.value}\n"
            f"Target: {event.target.label} ({event.target.path})\n"
            f"Payload: {event.raw_payload}\n"
            f"Current Risk Score: {current_score}\n"
            "Return JSON ONLY: {\"score\": int, \"rationale\": string}"
        )

        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt_content}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body)
                if resp.status_code == 200:
                    res_json = resp.json()
                    content = res_json["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return int(parsed.get("score", current_score)), parsed.get("rationale", "Groq evaluation completed.")
        except Exception as exc:
            warnings.warn(
                f"Groq API evaluation failed: {exc}. Tier 2 evaluation bypassed.",
                UserWarning
            )
            logger.warning(f"Groq API call failed: {exc}")
            return None
        return None
