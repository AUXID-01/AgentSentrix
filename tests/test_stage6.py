import os
import pytest
from core.agentsentrix.schema.enums import Verdict
from core.agentsentrix.bus.bus import EventBus
from core.agentsentrix.engine.evaluator import MultiTierEvaluator
from sim.scenario import SIMULATION_SCENARIOS, AgentPersona
from sim.runner import SimulationRunner, SimulationResult

def test_docker_sandbox_configuration():
    assert os.path.exists("docker/Dockerfile"), "Missing docker/Dockerfile"
    assert os.path.exists("docker/docker-compose.yml"), "Missing docker/docker-compose.yml"
    assert os.path.exists("docker/target_repo/.env"), "Missing docker/target_repo/.env"
    assert os.path.exists("docker/target_repo/README.md"), "Missing docker/target_repo/README.md"
    assert os.path.exists("docker/target_repo/src/main.py"), "Missing docker/target_repo/src/main.py"
    assert os.path.exists("docker/target_repo/tests/test_main.py"), "Missing docker/target_repo/tests/test_main.py"

def test_simulation_scenarios_definition():
    assert len(SIMULATION_SCENARIOS) == 4, "Expected 4 agent personas in simulation scenarios"
    
    agent_ids = [a.agent_id for a in SIMULATION_SCENARIOS]
    assert "refactorer-01" in agent_ids
    assert "test-runner-01" in agent_ids
    assert "mcp-installer-01" in agent_ids
    assert "rogue-01" in agent_ids

@pytest.mark.asyncio
async def test_simulation_runner_execution():
    bus = EventBus()
    evaluator = MultiTierEvaluator()
    runner = SimulationRunner(bus=bus, evaluator=evaluator, session_id="test_sim_stage6")

    result = await runner.run_scenario(auto_resolve_quarantine=True)

    assert isinstance(result, SimulationResult)
    assert result.session_id == "test_sim_stage6"
    assert result.total_agents == 4
    assert result.total_events >= 8

    # Check Verdict distribution
    assert result.allowed_count >= 3, f"Expected at least 3 ALLOWED events, got {result.allowed_count}"
    assert result.quarantined_count >= 1, f"Expected at least 1 QUARANTINED event, got {result.quarantined_count}"
    assert result.blocked_count >= 2, f"Expected at least 2 BLOCKED events, got {result.blocked_count}"

    # Verify Rogue agent exfiltration event is blocked
    rogue_blocked_events = [
        e for e in result.events
        if e["agent"]["id"] == "rogue-01" and e["risk"]["verdict"] == Verdict.BLOCKED.value
    ]
    assert len(rogue_blocked_events) >= 2, "Rogue agent credential exfiltration attempts should be BLOCKED"

@pytest.mark.asyncio
async def test_simulation_call_stack_lineage():
    bus = EventBus()
    evaluator = MultiTierEvaluator()
    runner = SimulationRunner(bus=bus, evaluator=evaluator, session_id="test_sim_lineage")

    result = await runner.run_scenario(auto_resolve_quarantine=True, step_delay_ms=0.0)

    # Group events by agent ID
    events_by_agent: dict[str, list[dict]] = {}
    for ev in result.events:
        agent_id = ev["agent"]["id"]
        events_by_agent.setdefault(agent_id, []).append(ev)

    # 1. Refactorer Agent (2 steps)
    refactorer_evs = events_by_agent["refactorer-01"]
    assert len(refactorer_evs) == 2
    assert refactorer_evs[0]["parent_id"] is None, "First step of agent should have parent_id=None"
    assert refactorer_evs[1]["parent_id"] == refactorer_evs[0]["id"], "Second step should link to first step ID"

    # 2. Rogue Agent (4 steps)
    rogue_evs = events_by_agent["rogue-01"]
    assert len(rogue_evs) == 4
    assert rogue_evs[0]["parent_id"] is None, "First step of rogue agent should have parent_id=None"
    assert rogue_evs[1]["parent_id"] == rogue_evs[0]["id"], "Step 2 parent_id should be Step 1 id"
    assert rogue_evs[2]["parent_id"] == rogue_evs[1]["id"], "Step 3 parent_id should be Step 2 id"
    assert rogue_evs[3]["parent_id"] == rogue_evs[2]["id"], "Step 4 parent_id should be Step 3 id"

@pytest.mark.asyncio
async def test_simulation_runner_delay_parameter():
    import time
    bus = EventBus()
    evaluator = MultiTierEvaluator()
    runner = SimulationRunner(bus=bus, evaluator=evaluator, session_id="test_sim_delay")

    start = time.perf_counter()
    result_fast = await runner.run_scenario(auto_resolve_quarantine=True, step_delay_ms=0.0)
    duration_fast = time.perf_counter() - start

    assert result_fast.total_events >= 8
    assert duration_fast < 1.0, f"Zero delay simulation should finish in under 1s, took {duration_fast:.3f}s"

