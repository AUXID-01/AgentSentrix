import re
from typing import Optional
from ..schema.enums import ActionType
from ..schema.events import AgentEvent, BlastRadius
from ..policy.loader import calculate_shannon_entropy, normalize_path

SENSITIVE_PATTERNS = [
    r"(?i)\.env",
    r"(?i)id_rsa",
    r"(?i)id_ed25519",
    r"(?i)aws/credentials",
    r"(?i)SECRET_KEY",
    r"(?i)API_KEY",
    r"(?i)PRIVATE_KEY",
    r"(?i)PASSWORD"
]

NON_REVERSIBLE_PATTERNS = [
    r"(?i)\brm\s+",
    r"(?i)\brmdir\s+",
    r"(?i)git\s+push.*(--force|-f)",
    r"(?i)truncate\s+",
    r"(?i)drop\s+table",
    r"(?i)curl\s+.*\|"
]

class BlastRadiusCalculator:
    """Calculates structural blast radius metrics for an AgentEvent."""

    def compute(self, event: AgentEvent) -> BlastRadius:
        target_path = event.target.path or event.target.label or ""
        norm_target_path = normalize_path(target_path)
        payload = event.raw_payload or ""
        norm_payload = normalize_path(payload)
        action_type = event.action_type

        # 1. Count files touched
        files_touched = 1 if target_path else 0
        # Check if payload references additional files
        file_matches = re.findall(r"[\w\./\-]+\.(?:py|js|ts|tsx|json|md|txt|env|yml|yaml)", payload)
        if file_matches:
            files_touched = max(files_touched, len(set(file_matches)))

        # 2. Reversibility check
        reversible = True
        for pat in NON_REVERSIBLE_PATTERNS:
            if re.search(pat, payload) or re.search(pat, target_path) or re.search(pat, norm_target_path):
                reversible = False
                break
        if action_type == ActionType.NET_EGRESS:
            reversible = False

        # 3. Secrets exposure check
        secrets_exposed = False
        for pat in SENSITIVE_PATTERNS:
            if re.search(pat, target_path) or re.search(pat, norm_target_path) or re.search(pat, payload) or re.search(pat, norm_payload):
                secrets_exposed = True
                break

        if not secrets_exposed and len(payload) > 25:
            for word in payload.split() :
                if len(word) >= 20 and calculate_shannon_entropy(word) > 3.8:
                    secrets_exposed = True
                    break

        # 4. Egress check
        egress = (action_type == ActionType.NET_EGRESS) or bool(event.target.host)
        if not egress:
            if re.search(r"(?i)(curl|wget|http://|https://)", payload):
                egress = True

        # 5. Composite Blast Radius Score calculation (0-100)
        score = 0
        score += min(files_touched * 10, 30)
        if not reversible:
            score += 30
        if secrets_exposed:
            score += 40
        if egress:
            score += 20

        score = min(max(score, 0), 100)

        return BlastRadius(
            files_touched=files_touched,
            reversible=reversible,
            secrets_exposed=secrets_exposed,
            egress=egress,
            score=score
        )
