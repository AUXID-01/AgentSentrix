import math
import re
import os
import logging
from typing import Optional
import yaml
from pydantic import BaseModel, Field
from ..schema.enums import Verdict, ActionType
from ..schema.events import AgentEvent

logger = logging.getLogger("agentsentrix.policy")

class PolicyRule(BaseModel):
    id: str
    name: str
    description: str = ""
    action_types: list[str] = Field(default_factory=list)
    score: int = Field(ge=0, le=100)
    verdict: Verdict
    path_patterns: list[str] = Field(default_factory=list)
    payload_patterns: list[str] = Field(default_factory=list)

class PolicyMatchResult(BaseModel):
    matched: bool = False
    max_score: int = 0
    verdict: Verdict = Verdict.ALLOWED
    matched_rule_ids: list[str] = Field(default_factory=list)
    rationale: str = ""

def calculate_shannon_entropy(data: str) -> float:
    """Compute Shannon Entropy of a string to detect high-entropy API keys or secret tokens."""
    if not data:
        return 0.0
    entropy = 0.0
    for x in set(data):
        p_x = data.count(x) / len(data)
        entropy -= p_x * math.log2(p_x)
    return entropy

def normalize_path(path_str: str) -> str:
    """Normalize file paths by resolving relative components (., ..) and unifying slashes."""
    if not path_str:
        return ""
    cleaned = path_str.replace("\\", "/")
    try:
        norm = os.path.normpath(cleaned).replace("\\", "/")
        return norm
    except Exception:
        return cleaned

class PolicyLoader:
    """Loads and compiles deterministic YAML policy rules for Tier 0 evaluation."""

    def __init__(self, rules_path: Optional[str] = None) -> None:
        if rules_path is None:
            base_dir = os.path.dirname(__file__)
            rules_path = os.path.join(base_dir, "rules.yaml")

        self.rules_path = rules_path
        self.rules: list[PolicyRule] = []
        self._compiled_path_regexes: dict[str, list[re.Pattern]] = {}
        self._compiled_payload_regexes: dict[str, list[re.Pattern]] = {}
        self.load_rules()

    def load_rules(self) -> None:
        """Load and compile YAML rules."""
        if not os.path.exists(self.rules_path):
            logger.warning(f"Rules YAML file not found at {self.rules_path}. Operating with empty ruleset.")
            return

        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)

            raw_rules = raw_data.get("rules", []) if isinstance(raw_data, dict) else []
            self.rules = []
            self._compiled_path_regexes.clear()
            self._compiled_payload_regexes.clear()

            for rule_dict in raw_rules:
                rule = PolicyRule.model_validate(rule_dict)
                self.rules.append(rule)

                # Compile path patterns
                self._compiled_path_regexes[rule.id] = [
                    re.compile(pat) for pat in rule.path_patterns
                ]
                # Compile payload patterns
                self._compiled_payload_regexes[rule.id] = [
                    re.compile(pat) for pat in rule.payload_patterns
                ]

            logger.info(f"Successfully loaded {len(self.rules)} rules from {self.rules_path}")
        except Exception as exc:
            logger.error(f"Failed to parse policy rules from {self.rules_path}: {exc}", exc_info=True)

    def evaluate(self, event: AgentEvent) -> PolicyMatchResult:
        """Evaluate an incoming AgentEvent against all loaded rules and Shannon entropy checks."""
        matched_rules: list[PolicyRule] = []
        raw_target_path = event.target.path or event.target.host or event.target.label or ""
        norm_target_path = normalize_path(raw_target_path)
        payload = event.raw_payload or ""
        norm_payload = normalize_path(payload)
        action_val = event.action_type.value if hasattr(event.action_type, "value") else str(event.action_type)

        # Check YAML rules
        for rule in self.rules:
            # Check action_type filter if specified
            if rule.action_types and action_val not in rule.action_types:
                continue

            hit = False
            # Check path patterns against raw and normalized target path
            for compiled_pat in self._compiled_path_regexes.get(rule.id, []):
                if compiled_pat.search(raw_target_path) or compiled_pat.search(norm_target_path):
                    hit = True
                    break

            # Check payload patterns against raw and normalized payload if not already hit
            if not hit:
                for compiled_pat in self._compiled_payload_regexes.get(rule.id, []):
                    if compiled_pat.search(payload) or compiled_pat.search(norm_payload):
                        hit = True
                        break

            if hit:
                matched_rules.append(rule)

        # High Entropy Secret Detection (for API keys / secrets in payload)
        entropy_rule_matched = False
        if len(payload) > 25:
            words = payload.split()
            for word in words:
                if len(word) >= 20 and calculate_shannon_entropy(word) > 3.8:
                    entropy_rule_matched = True
                    break

        if not matched_rules and not entropy_rule_matched:
            return PolicyMatchResult(matched=False, max_score=0, verdict=Verdict.ALLOWED)

        matched_rule_ids = [r.id for r in matched_rules]
        if entropy_rule_matched:
            matched_rule_ids.append("SEC-009-ENTROPY-SECRET")

        # Highest score rule determines the verdict
        max_score = max([r.score for r in matched_rules] + ([90] if entropy_rule_matched else [0]))
        
        # Determine highest severity verdict
        if max_score >= 75:
            verdict = Verdict.BLOCKED
        elif max_score >= 40:
            verdict = Verdict.QUARANTINED
        else:
            verdict = Verdict.ALLOWED

        rationales = [f"Rule '{r.name}' ({r.id}) triggered" for r in matched_rules]
        if entropy_rule_matched:
            rationales.append("High Shannon entropy string detected in action payload (possible secret leak)")

        return PolicyMatchResult(
            matched=True,
            max_score=max_score,
            verdict=verdict,
            matched_rule_ids=matched_rule_ids,
            rationale="; ".join(rationales)
        )
