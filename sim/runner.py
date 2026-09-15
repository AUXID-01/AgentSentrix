import argparse
import asyncio
import uuid
import logging
import time
from typing import Optional
from pydantic import BaseModel, Field

from core.agentsentrix.schema.enums import Sensor, Verdict
from core.agentsentrix.schema.events import AgentEvent, AgentRef, Target, RiskAssessment
from core.agentsentrix.engine.evaluator import MultiTierEvaluator
from core.agentsentrix.bus.bus import EventBus
from core.agentsentrix.bus.sinks.duckdb_sink import DuckDBSink
from core.agentsentrix.bus.sinks.jsonl_sink import JSONLSink
from core.agentsentrix.proxy.quarantine import QuarantineManager
from core.agentsentrix.projection.graph_projection import GraphProjection
from sim.scenario import SIMULATION_SCENARIOS, AgentPersona, StepDefinition

logger = logging.getLogger("agentsentrix.sim.runner")

class SimulationResult(BaseModel):
    session_id: str
    total_agents: int
    total_events: int
    allowed_count: int = 0
    quarantined_count: int = 0
    blocked_count: int = 0
    events: list[dict] = Field(default_factory=list)

class SimulationRunner:
    """Runs the 4-agent LangGraph security scenario simulation against AgentSentrix."""

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        evaluator: Optional[MultiTierEvaluator] = None,
        quarantine_mgr: Optional[QuarantineManager] = None,
        session_id: Optional[str] = None
    ) -> None:
        self.bus = bus or EventBus()
        self.evaluator = evaluator or MultiTierEvaluator()
        self.quarantine_mgr = quarantine_mgr or QuarantineManager()
        self.session_id = session_id or f"sim_session_{int(time.time())}"

    async def run_scenario(
        self,
        auto_resolve_quarantine: bool = True,
        step_delay_ms: float = 0.0
    ) -> SimulationResult:
        """Execute all 4 agent scenario personas and stream telemetry."""
        logger.info(f"Starting AgentSentrix simulation scenario [Session: {self.session_id}]")
        
        events_emitted: list[AgentEvent] = []
        allowed_cnt = 0
        quarantined_cnt = 0
        blocked_cnt = 0

        for persona in SIMULATION_SCENARIOS:
            logger.info(f"Running persona: {persona.name} ({persona.agent_id}) [{persona.model}]")
            last_event_id: Optional[str] = None
            
            for step in persona.steps:
                event = AgentEvent(
                    id=f"evt_sim_{uuid.uuid4().hex[:12]}",
                    session_id=self.session_id,
                    sensor=Sensor.SDK_MIDDLEWARE,
                    agent=AgentRef(
                        id=persona.agent_id,
                        name=persona.name,
                        model=persona.model,
                        framework=persona.framework,
                        task=persona.task_prompt
                    ),
                    action_type=step.action_type,
                    target=Target(
                        kind=step.target_kind,
                        label=step.target_label,
                        path=step.target_path
                    ),
                    raw_payload=step.payload,
                    task_context=persona.task_prompt,
                    risk=RiskAssessment(score=0, verdict=Verdict.ALLOWED),
                    parent_id=last_event_id
                )

                # Assess Risk
                risk, blast = await self.evaluator.assess(event)
                event.risk = risk
                event.blast_radius = blast

                # Publish Event to Bus
                await self.bus.publish(event)
                events_emitted.append(event)

                # Track previous event for call stack lineage chain
                last_event_id = event.id

                # Track Counts
                if risk.verdict == Verdict.ALLOWED:
                    allowed_cnt += 1
                elif risk.verdict == Verdict.QUARANTINED:
                    quarantined_cnt += 1
                    if auto_resolve_quarantine:
                        # Create and resolve quarantine state
                        self.quarantine_mgr.create_quarantine_future(event.id, event.model_dump(mode="json"))
                        self.quarantine_mgr.resolve_quarantine(event.id, Verdict.QUARANTINED, "Simulation auto-held")
                elif risk.verdict == Verdict.BLOCKED:
                    blocked_cnt += 1

                # Throttling delay for realistic animation / live visual streaming
                if step_delay_ms > 0:
                    await asyncio.sleep(step_delay_ms / 1000.0)

        logger.info(
            f"Simulation completed for session {self.session_id}: "
            f"Total: {len(events_emitted)}, Allowed: {allowed_cnt}, "
            f"Quarantined: {quarantined_cnt}, Blocked: {blocked_cnt}"
        )

        return SimulationResult(
            session_id=self.session_id,
            total_agents=len(SIMULATION_SCENARIOS),
            total_events=len(events_emitted),
            allowed_count=allowed_cnt,
            quarantined_count=quarantined_cnt,
            blocked_count=blocked_cnt,
            events=[e.model_dump(mode="json") for e in events_emitted]
        )

def main():
    parser = argparse.ArgumentParser(description="AgentSentrix Multi-Agent Simulation Driver")
    parser.add_argument("--delay-ms", type=float, default=800.0, help="Delay between agent steps in milliseconds (default: 800)")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed multiplier for simulation execution (default: 1.0)")
    args = parser.parse_args()

    effective_delay_ms = args.delay_ms / max(args.speed, 0.1)

    bus = EventBus()
    duckdb_sink = DuckDBSink(db_path="data/agentsentrix.duckdb")
    jsonl_sink = JSONLSink(target_dir="data/sessions")
    projection = GraphProjection()

    bus.subscribe(duckdb_sink)
    bus.subscribe(jsonl_sink)
    bus.subscribe(projection)

    runner = SimulationRunner(bus=bus)
    res = asyncio.run(runner.run_scenario(step_delay_ms=effective_delay_ms))

    duckdb_sink.close()

    print("\n================ AGENTSENTRIX SIMULATION RESULT ================")
    print(f"Session ID        : {res.session_id}")
    print(f"Total Agents Run  : {res.total_agents}")
    print(f"Total Telemetry   : {res.total_events} events")
    print(f"Step Delay        : {effective_delay_ms:.1f} ms")
    print(f"  • ALLOWED       : {res.allowed_count}")
    print(f"  • QUARANTINED   : {res.quarantined_count}")
    print(f"  • BLOCKED       : {res.blocked_count}")
    print("=================================================================\n")

if __name__ == "__main__":
    main()

