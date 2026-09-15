# AgentSentrix - Stage 2 Implementation & Developer Usage Guide

This document provides a complete technical guide to **Stage 2** of **AgentSentrix**: the Multi-Tier Risk Evaluation Engine, Deterministic Policy Rules, Path Traversal Evasion Guard, Shannon Entropy Secret Detection, Structural Blast Radius Calculator, and Redis Verdict Caching.

---

## 1. Architectural Overview

Stage 2 sits at the heart of the AgentSentrix inline interceptor, transforming raw agent action payloads into structured risk verdicts (`ALLOWED`, `QUARANTINED`, `BLOCKED`) and quantitative blast radius metrics (0–100).

```
                            [ AgentEvent Payload ]
                                      │
                                      ▼
                        ┌──────────────────────────┐
                        │    SHA-256 Action Hash   │
                        └─────────────┬────────────┘
                                      │
                         ┌────────────┴────────────┐
                         │   Redis State Cache     │ ──(Hit)──► Return Cached Verdict (<1ms)
                         └────────────┬────────────┘
                                      │ (Miss)
                                      ▼
                     ┌─────────────────────────────────┐
                     │   Tier 0: Policy Loader & YAML  │ (~1ms)
                     │     + Shannon Entropy Check     │
                     └────────────────┬────────────────┘
                                      │
          ┌───────────────────────────┴──────────────────────────┐
          │ High Confidence (Score >= 75 or <= 20)              │ Ambiguous Band (Score 30-70)
          ▼                                                     ▼
 [ Return Immediate Verdict ]                        ┌─────────────────────┐
                                                     │ Tier 1: Ollama      │ (~50ms)
                                                     │ Local Classifier    │
                                                     └──────────┬──────────┘
                                                                │
                                                     ┌──────────┴──────────┐
                                                     │ Tier 2: Groq LLM    │ (~300ms)
                                                     │ Structured Judge    │
                                                     └──────────┬──────────┘
                                                                │
                                                                ▼
                                                    [ Composite Score & ]
                                                    [ Blast Radius Calc ]
```

---

## 2. Core Components & Functionality

### 2.1 Deterministic Policy Rules (`core/agentsentrix/policy/rules.yaml`)
Defined in YAML with pre-compiled regular expressions matching specific action types, target file paths, and execution command strings:

| Policy ID | Category | Severity / Score | Target Action | Detection Pattern / Description |
| :--- | :--- | :--- | :--- | :--- |
| `SEC-001-ENV-READ` | Environment Secrets | 95 (BLOCKED) | File Read/Write, Shell, Tool Call | Accessing `.env`, `.env.local`, `.env.*` files or `cat .env` commands. |
| `SEC-002-SSH-KEY` | Credentials Exfiltration | 95 (BLOCKED) | File Read, Shell, Tool Call | Accessing `~/.ssh/id_rsa`, `id_ed25519`, `authorized_keys`, `known_hosts`. |
| `SEC-003-AWS-CRED` | Cloud Credentials | 95 (BLOCKED) | File Read, Shell, Tool Call | Accessing `~/.aws/credentials`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`. |
| `SEC-004-RM-RF` | Destructive Execution | 100 (BLOCKED) | Shell, Tool Call | Destructive commands: `rm -rf /`, `rm -rf ~`, `rm -rf .`, `rmdir /s /q`. |
| `SEC-005-CURL-SH` | Remote Piping | 90 (BLOCKED) | Shell, Tool Call | Piping web downloads directly to shell: `curl \| sh`, `wget \| bash`, `curl \| python`. |
| `SEC-006-GIT-FORCE` | Dangerous Git Operations | 85 (QUARANTINED) | Git Op, Shell, Tool Call | Forced git pushes (`git push --force`, `git push -f`) or push to non-origin remotes. |
| `SEC-007-BASE64-EXEC` | Obfuscation | 80 (QUARANTINED) | Shell, Tool Call | Obfuscated Base64 shell commands: `base64 -d \| bash`, `eval $(echo ... \| base64)`. |
| `SEC-008-NET-EGRESS` | Network Egress | 75 (QUARANTINED) | Net Egress, Shell, Tool Call | Outbound HTTP/HTTPS requests targeting raw IP addresses. |
| `SEC-009-ENTROPY-SECRET` | Key Detection | 90 (BLOCKED) | All Actions | High Shannon entropy strings (>3.8) longer than 20 characters in payload. |
| `SEC-010-SAFE-READ` | Safe Document Read | 10 (ALLOWED) | File Read, Tool Call | Standard source files and documentation (`*.md`, `*.json`, `*.py`, `*.ts`, `*.tsx`). |

---

### 2.2 Path Traversal & Evasion Guard (`core/agentsentrix/policy/loader.py`)
To prevent evasion techniques using relative path dot-segments or duplicate slashes (e.g. `cat ./subdir/../../.env` or `cat /repo//.env`), the `PolicyLoader` normalizes paths before evaluation:

```python
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
```

---

### 2.3 Structural Blast Radius Calculator (`core/agentsentrix/engine/blast_radius.py`)
Computes quantitative structural impact for every event based on 4 independent dimensions:

1. **Files Touched**: Count of distinct file paths referenced in the target or payload string (`min(count * 10, 30)` points).
2. **Reversibility (`reversible`)**: Evaluated as `False` for destructive commands (`rm`, `truncate`, `drop table`, `git push -f`, `NET_EGRESS`) (+30 points).
3. **Secret Exposure (`secrets_exposed`)**: Evaluated as `True` if sensitive file patterns or high Shannon entropy tokens are present (+40 points).
4. **Network Egress (`egress`)**: Evaluated as `True` for `NET_EGRESS` or external IP/URL destinations (+20 points).
5. **Score**: Clamped aggregate score between `0` and `100`.

---

### 2.4 Multi-Tier Risk Evaluator (`core/agentsentrix/engine/evaluator.py`)
Unified `assess(event: AgentEvent) -> tuple[RiskAssessment, BlastRadius]` method implementing:

- **Tier 0 (~1ms)**: Immediate YAML policy matcher and entropy scanner. Scores $\ge 75$ or $\le 20$ take the fast-path exit.
- **Tier 1 (~50ms)**: Async HTTP calls to local Ollama endpoint (`http://localhost:11434/api/generate`) with model `qwen2.5-coder:1.5b` evaluating tool prompt injection and task intent drift.
- **Tier 2 (~300ms)**: Async HTTP calls to Groq API (`https://api.groq.com/openai/v1/chat/completions`) for ambiguous scores (30–70) returning structured JSON `{score, rationale}`.
- **Verdict Threshold Mapping**:
  - `0 – 39`: `ALLOWED`
  - `40 – 74`: `QUARANTINED`
  - `75 – 100`: `BLOCKED`
- **Sub-Second Redis Caching**: Hashes `action_type:target:raw_payload` with SHA-256 and stores/retrieves `RiskAssessment` in Redis (`ttl=3600`).
- **Resilience Policy**: Emits explicit `UserWarning`s when Ollama or Groq are offline/unreachable and falls back safely to Tier 0 rule scores without process crashes.

---

## 3. How to Use Stage 2 Components in Code

### 3.1 Policy Evaluation Example
```python
from core.agentsentrix.policy.loader import PolicyLoader
from core.agentsentrix.schema.enums import ActionType, NodeKind, Verdict, Sensor
from core.agentsentrix.schema.events import AgentEvent, AgentRef, Target, RiskAssessment

loader = PolicyLoader()

event = AgentEvent(
    id="evt_001",
    session_id="session_01",
    sensor=Sensor.MCP_PROXY,
    agent=AgentRef(id="agent_1", name="Coder Agent"),
    action_type=ActionType.FILE_READ,
    target=Target(kind=NodeKind.FILE, label=".env", path="./subdir/../../.env"),
    raw_payload="cat ./subdir/../../.env",
    risk=RiskAssessment(score=0, verdict=Verdict.ALLOWED)
)

result = loader.evaluate(event)
print(f"Matched: {result.matched}, Score: {result.max_score}, Verdict: {result.verdict}")
# Output: Matched: True, Score: 95, Verdict: Verdict.BLOCKED
```

### 3.2 Full Multi-Tier Assessment Example
```python
import asyncio
from core.agentsentrix.engine.evaluator import MultiTierEvaluator
from core.agentsentrix.bus.cache import StateCache

async def main():
    cache = StateCache() # Connects to Redis at localhost:6379
    evaluator = MultiTierEvaluator(cache=cache)

    risk, blast = await evaluator.assess(event)

    print(f"Final Score: {risk.score}")
    print(f"Verdict: {risk.verdict}")
    print(f"Tier Scores: {risk.tier_scores}")
    print(f"Rationale: {risk.rationale}")
    print(f"Blast Radius Score: {blast.score} (Reversible: {blast.reversible}, Secrets: {blast.secrets_exposed})")

asyncio.run(main())
```

---

## 4. Verification & Testing

### 4.1 Prerequisites
1. Redis container running via Docker:
   ```powershell
   docker run -d -p 6379:6379 --name agentsentrix-redis redis:alpine
   ```
2. Python Virtual Environment (`venv`) activated.

### 4.2 Verification Commands

#### 1. Verify Redis Connection:
```powershell
venv\Scripts\python.exe -c "import redis; r = redis.Redis(host='localhost', port=6379); print('Redis Ping:', r.ping())"
```
*Expected Output:* `Redis Ping: True`

#### 2. Verify Policy Rules Count:
```powershell
venv\Scripts\python.exe -c "from core.agentsentrix.policy.loader import PolicyLoader; loader = PolicyLoader(); print('Rules Loaded:', len(loader.rules))"
```
*Expected Output:* `Rules Loaded: 9`

#### 3. Run Automated Pytest Suite (Stage 1 + Stage 2):
```powershell
venv\Scripts\pytest.exe tests/test_stage1.py tests/test_stage2.py -v
```

---

## 5. Automated Test Matrix

| Test Function | Target Verified | Pass Criteria |
| :--- | :--- | :--- |
| `test_stage1_complete_flow` | Bus, DuckDB, JSONL, Ring Buffer, Redis | 10 events delivered sequentially, DuckDB count = 10, JSONL line count = 10, cache hits verified. |
| `test_shannon_entropy` | Shannon Entropy Secret Detection | Low entropy < 1.0, high-entropy hex string > 3.8. |
| `test_tier0_yaml_rules` | YAML Policy Matcher | `.env` read -> 95 BLOCKED, `rm -rf` -> 100 BLOCKED, `curl \| sh` -> 90 BLOCKED, safe read -> 10 ALLOWED. |
| `test_blast_radius_calculator` | Structural Blast Metrics | `rm -rf` -> `reversible=False`, `.env` -> `secrets_exposed=True`, safe read -> `reversible=True`. |
| `test_multitier_evaluator_full_flow` | Full Multi-Tier Flow & Cache | First call returns `cached=False`, second call returns `cached=True` with identical verdict. |
| `test_resilience_warning_emission` | Unreachable LLM Endpoints | Offline Ollama/Groq emit `UserWarning`, zero exceptions raised, valid assessment returned. |
| `test_path_traversal_evasion_prevention` | Path Traversal Evasion Guard | `./subdir/../../.env` and `/repo//.env` matched by `SEC-001-ENV-READ` (`Verdict.BLOCKED`). |
| `test_tier1_tier2_mock_responses` | Ambiguous Band Structured JSON Unpacking | Ollama (50) + Groq (80) JSON responses parsed, setting `t1_local=50`, `t2_llm=80`, composite score `80` (`BLOCKED`). |
