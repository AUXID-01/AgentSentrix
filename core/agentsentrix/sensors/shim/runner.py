import sys
import os
import shutil
import asyncio
import uuid
import logging
import subprocess
from typing import Optional

from ...schema.enums import Sensor, ActionType, NodeKind, Verdict
from ...schema.events import AgentEvent, AgentRef, Target, RiskAssessment
from ...engine.evaluator import MultiTierEvaluator
from ...bus.bus import EventBus
from ...proxy.quarantine import QuarantineManager
from ...bus.cache import StateCache

logger = logging.getLogger("agentsentrix.sensors.shim.runner")

def find_real_binary(cmd_name: str) -> Optional[str]:
    """
    Locate the real executable binary on PATH, explicitly excluding
    any AgentSentrix shim directories to prevent infinite recursion.
    """
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    clean_path_dirs = [
        d for d in path_dirs
        if d and "agentsentrix" not in d.lower() and "shim" not in d.lower()
    ]
    clean_path = os.pathsep.join(clean_path_dirs)

    # Search for system binary in clean PATH
    real_bin = shutil.which(cmd_name, path=clean_path)
    if real_bin:
        return real_bin

    # On Windows, try extension variations (.exe, .cmd, .bat)
    if sys.platform == "win32" and not cmd_name.endswith((".exe", ".cmd", ".bat")):
        for ext in [".exe", ".cmd", ".bat"]:
            real_bin = shutil.which(cmd_name + ext, path=clean_path)
            if real_bin:
                return real_bin

    return None

class ShimRunner:
    """Intercepts shell command executions, evaluates security risk, and forwards or blocks."""

    def __init__(
        self,
        evaluator: Optional[MultiTierEvaluator] = None,
        bus: Optional[EventBus] = None,
        quarantine_mgr: Optional[QuarantineManager] = None
    ) -> None:
        self.bus = bus or EventBus()
        self.evaluator = evaluator or MultiTierEvaluator()
        self.quarantine_mgr = quarantine_mgr or QuarantineManager()

    async def execute(self, cmd_name: str, args: list[str]) -> int:
        raw_payload = f"{cmd_name} {' '.join(args)}".strip()
        real_bin = find_real_binary(cmd_name)

        # Map ActionType based on command name
        if cmd_name == "git":
            action_type = ActionType.GIT_OP
        elif cmd_name in ("curl", "wget", "aws"):
            action_type = ActionType.NET_EGRESS
        elif cmd_name in ("rm", "rmdir"):
            action_type = ActionType.SHELL_EXEC
        else:
            action_type = ActionType.SHELL_EXEC

        event = AgentEvent(
            id=f"evt_shim_{uuid.uuid4().hex[:12]}",
            session_id=os.getenv("AGENTSENTRIX_SESSION_ID", "shim_session"),
            sensor=Sensor.SHELL_SHIM,
            agent=AgentRef(
                id=os.getenv("AGENTSENTRIX_AGENT_ID", "shell_agent"),
                name="Shell Subprocess",
                framework="shell_shim"
            ),
            action_type=action_type,
            target=Target(kind=NodeKind.SHELL, label=cmd_name, path=real_bin or cmd_name),
            raw_payload=raw_payload,
            risk=RiskAssessment(score=0, verdict=Verdict.ALLOWED)
        )

        # 1. Assess Risk
        risk, blast_radius = await self.evaluator.assess(event)
        event.risk = risk
        event.blast_radius = blast_radius

        # 2. Publish Telemetry to EventBus
        await self.bus.publish(event)

        # 3. Handle Verdict
        if risk.verdict == Verdict.BLOCKED:
            sys.stderr.write(
                f"[AgentSentrix] POLICY BLOCKED: Shell command '{raw_payload}' was refused.\n"
                f"  Risk Score: {risk.score}/100 | Policy ID: {', '.join(risk.policy_ids) or 'N/A'}\n"
                f"  Rationale: {risk.rationale}\n"
            )
            sys.stderr.flush()
            return 1

        elif risk.verdict == Verdict.QUARANTINED:
            sys.stderr.write(
                f"[AgentSentrix] Action held for human approval (Event ID: {event.id}). Resolve at http://localhost:7777...\n"
                f"  Risk Score: {risk.score}/100 | Rationale: {risk.rationale}\n"
            )
            sys.stderr.flush()
            
            future = self.quarantine_mgr.create_quarantine_future(event.id, event.model_dump(mode="json"))
            try:
                # Wait for resolution (or timeout in CLI mode)
                resolution = await asyncio.wait_for(future, timeout=30.0)
                res_verdict = resolution.get("verdict")
                if res_verdict in (Verdict.ALLOWED.value, Verdict.ALLOWED):
                    sys.stderr.write("[AgentSentrix] QUARANTINE APPROVED by operator. Executing...\n")
                    sys.stderr.flush()
                else:
                    sys.stderr.write("[AgentSentrix] QUARANTINE DENIED by operator. Aborting execution.\n")
                    sys.stderr.flush()
                    return 1
            except (asyncio.CancelledError, KeyboardInterrupt):
                sys.stderr.write("\n[AgentSentrix] QUARANTINE CANCELLED by developer (Ctrl+C). Aborting execution.\n")
                sys.stderr.flush()
                self.quarantine_mgr.resolve_quarantine(event.id, Verdict.BLOCKED, "Cancelled by user (Ctrl+C)")
                return 1
            except asyncio.TimeoutError:
                sys.stderr.write("[AgentSentrix] QUARANTINE TIMEOUT: No approval received within 30s. Defaulting to DENIED.\n")
                sys.stderr.flush()
                self.quarantine_mgr.resolve_quarantine(event.id, Verdict.BLOCKED, "Quarantine timeout")
                return 1

        # 4. Forward execution if ALLOWED
        if not real_bin:
            sys.stderr.write(f"[AgentSentrix] ERROR: System binary '{cmd_name}' not found on PATH.\n")
            sys.stderr.flush()
            return 127

        try:
            # Clean PATH environment to avoid calling shims recursively
            clean_env = os.environ.copy()
            clean_path_dirs = [
                d for d in clean_env.get("PATH", "").split(os.pathsep)
                if d and "agentsentrix" not in d.lower() and "shim" not in d.lower()
            ]
            clean_env["PATH"] = os.pathsep.join(clean_path_dirs)

            # Pass stdin safely to support pipes in real terminals and avoid pseudofile errors in pytest
            stdin_arg = None
            if hasattr(sys.stdin, "fileno"):
                try:
                    sys.stdin.fileno()
                    stdin_arg = sys.stdin
                except Exception:
                    stdin_arg = None

            res = subprocess.run([real_bin] + args, env=clean_env, stdin=stdin_arg)
            return res.returncode
        except Exception as exc:
            sys.stderr.write(f"[AgentSentrix] Execution error forwarding to '{real_bin}': {exc}\n")
            sys.stderr.flush()
            return 1

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python -m core.agentsentrix.sensors.shim.runner <cmd_name> [args...]\n")
        sys.exit(1)

    cmd_name = sys.argv[1]
    cmd_args = sys.argv[2:]

    runner = ShimRunner()
    try:
        exit_code = asyncio.run(runner.execute(cmd_name, cmd_args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.stderr.write("\n[AgentSentrix] QUARANTINE CANCELLED by developer (Ctrl+C). Aborting execution.\n")
        sys.stderr.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
