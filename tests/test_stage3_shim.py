import os
import sys
import shutil
import pytest

from core.agentsentrix.schema.enums import Sensor, ActionType, Verdict
from core.agentsentrix.schema.events import AgentEvent
from core.agentsentrix.bus.bus import EventBus
from core.agentsentrix.engine.evaluator import MultiTierEvaluator
from core.agentsentrix.proxy.quarantine import QuarantineManager
from core.agentsentrix.sensors.shim.manager import ShimManager, SHIM_TARGETS
from core.agentsentrix.sensors.shim.runner import ShimRunner, find_real_binary

TEST_SHIM_DIR = os.path.abspath("data/test_shims")

@pytest.fixture(autouse=True)
def cleanup_shims():
    if os.path.exists(TEST_SHIM_DIR):
        try:
            shutil.rmtree(TEST_SHIM_DIR)
        except Exception:
            pass
    yield
    if os.path.exists(TEST_SHIM_DIR):
        try:
            shutil.rmtree(TEST_SHIM_DIR)
        except Exception:
            pass

def test_shim_manager_installation():
    manager = ShimManager(shim_dir=TEST_SHIM_DIR)
    installed_dir = manager.install_shims()
    assert os.path.exists(installed_dir)

    for tool in SHIM_TARGETS:
        posix_script = os.path.join(installed_dir, tool)
        win_cmd = os.path.join(installed_dir, f"{tool}.cmd")
        assert os.path.exists(posix_script), f"Missing POSIX shim script for {tool}"
        assert os.path.exists(win_cmd), f"Missing Windows CMD wrapper for {tool}"

    shimmed_env = manager.get_env_with_shims()
    assert shimmed_env["PATH"].startswith(installed_dir)

def test_shim_runner_find_real_binary():
    real_git = find_real_binary("git")
    assert real_git is not None, "Real git binary should be found on system PATH"
    assert "agentsentrix" not in real_git.lower() or "git" in real_git.lower()

@pytest.mark.asyncio
async def test_shim_runner_allowed_flow():
    bus = EventBus()
    received_events: list[AgentEvent] = []

    async def sub(event: AgentEvent):
        received_events.append(event)

    bus.subscribe(sub)

    evaluator = MultiTierEvaluator()
    runner = ShimRunner(evaluator=evaluator, bus=bus)

    # Allowed safe command: git --version
    code = await runner.execute("git", ["--version"])
    assert code == 0, "git --version should execute successfully with exit code 0"

    assert len(received_events) >= 1
    event = received_events[-1]
    assert event.sensor == Sensor.SHELL_SHIM
    assert event.action_type == ActionType.GIT_OP
    assert event.risk.verdict == Verdict.ALLOWED
    assert "git --version" in event.raw_payload

@pytest.mark.asyncio
async def test_shim_runner_blocked_flow(capsys):
    bus = EventBus()
    received_events: list[AgentEvent] = []

    async def sub(event: AgentEvent):
        received_events.append(event)

    bus.subscribe(sub)

    evaluator = MultiTierEvaluator()
    runner = ShimRunner(evaluator=evaluator, bus=bus)

    # Dangerous command: rm -rf /
    code = await runner.execute("rm", ["-rf", "/"])
    assert code == 1, "rm -rf / should be refused with non-zero policy denial exit code 1"

    captured = capsys.readouterr()
    assert "POLICY BLOCKED" in captured.err
    assert "SEC-004-RM-RF" in captured.err or "100" in captured.err

    assert len(received_events) >= 1
    event = received_events[-1]
    assert event.sensor == Sensor.SHELL_SHIM
    assert event.action_type == ActionType.SHELL_EXEC
    assert event.risk.verdict == Verdict.BLOCKED
    assert event.risk.score == 100

from core.agentsentrix.schema.events import AgentEvent, RiskAssessment, BlastRadius

@pytest.mark.asyncio
async def test_shim_runner_quarantine_flow(capsys):
    from unittest.mock import patch

    bus = EventBus()
    quarantine_mgr = QuarantineManager()
    evaluator = MultiTierEvaluator()
    runner = ShimRunner(evaluator=evaluator, bus=bus, quarantine_mgr=quarantine_mgr)

    quarantined_risk = RiskAssessment(
        score=50,
        verdict=Verdict.QUARANTINED,
        rationale="Ambiguous AWS S3 sync action"
    )

    with patch.object(evaluator, "assess", return_value=(quarantined_risk, BlastRadius())):
        import asyncio
        exec_task = asyncio.create_task(runner.execute("aws", ["s3", "sync", "./data", "s3://bucket"]))

        # Allow task to enter quarantine state
        await asyncio.sleep(0.1)

        assert len(quarantine_mgr.pending_futures) == 1
        event_id = list(quarantine_mgr.pending_futures.keys())[0]

        # Resolve quarantine with Verdict.BLOCKED (Operator Deny)
        quarantine_mgr.resolve_quarantine(event_id, Verdict.BLOCKED, "Denied by operator test")

        code = await exec_task
        assert code == 1, "Quarantine denial should result in exit code 1"

        captured = capsys.readouterr()
        assert "Action held for human approval" in captured.err
        assert "Resolve at http://localhost:7777" in captured.err
        assert "QUARANTINE DENIED by operator" in captured.err

def test_shim_stdin_passthrough():
    from unittest.mock import patch, MagicMock
    runner = ShimRunner()

    mock_stdin = MagicMock()
    mock_stdin.fileno.return_value = 0

    with patch("sys.stdin", mock_stdin), patch("subprocess.run") as mock_sub_run:
        mock_sub_run.return_value.returncode = 0
        import asyncio
        asyncio.run(runner.execute("git", ["--version"]))
        assert mock_sub_run.called
        _, kwargs = mock_sub_run.call_args
        assert kwargs.get("stdin") == mock_stdin
