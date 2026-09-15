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

        from sim.langgraph_agents import build_agent_stategraph, SimulatedToolCall, HumanMessage
        from core.agentsentrix.sdk import AgentSentrixCallbackHandler, SecurityBlockError

        for persona in SIMULATION_SCENARIOS:
            print(f"\n[LANGGRAPH ENGINE] -- Instantiating StateGraph for Agent Persona: {persona.name} ({persona.agent_id})")
            print(f"                   Framework: {persona.framework} | Model: {persona.model} | Task: '{persona.task_prompt}'")
            
            # Attach public SDK Callback Handler
            sdk_handler = AgentSentrixCallbackHandler(
                server_url="http://localhost:7777",
                agent_id=persona.agent_id,
                agent_name=persona.name
            )

            # Construct LangGraph StateGraph workflow
            tool_calls = [
                SimulatedToolCall(s.action_type, s.target_kind, s.target_label, s.target_path, s.payload)
                for s in persona.steps
            ]
            graph_app = build_agent_stategraph(persona.agent_id, persona.name, tool_calls)

            # Initial state for LangGraph workflow execution
            langgraph_state = {
                "messages": [HumanMessage(content=persona.task_prompt)],
                "agent_id": persona.agent_id,
                "persona_name": persona.name,
                "current_step": 0,
                "session_id": self.session_id,
                "events_generated": []
            }

            last_event_id: Optional[str] = None
            
            for step_idx, step in enumerate(persona.steps, start=1):
                # Public SDK Callback Handler Interception Hook
                try:
                    sdk_handler.on_tool_start({"name": step.action_type.value}, step.payload)
                except SecurityBlockError:
                    pass

                # Execute LangGraph node step
                langgraph_state = await graph_app.ainvoke(langgraph_state)
                
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

                # Assess Risk via MultiTierEvaluator
                risk, blast = await self.evaluator.assess(event)
                event.risk = risk
                event.blast_radius = blast

                # Detailed Developer Telemetry Log
                print(
                    f"  |- [STEP #{step_idx}] Tool: {step.action_type.value:<12} | Target: {step.target_label:<20} "
                    f"| Verdict: {risk.verdict.value.upper():<11} | Score: {risk.score:3d}/100 | Blast: {blast.score}"
                )

                # Publish Event to Bus
                await self.bus.publish(event)
                events_emitted.append(event)

                # Send event to running server for live 3D WebSocket visual streaming (non-blocking)
                async def _post_event_bg(evt_data: dict):
                    try:
                        import urllib.request, json, asyncio
                        payload = json.dumps(evt_data).encode("utf-8")
                        req = urllib.request.Request(
                            "http://localhost:7777/events/ingest",
                            data=payload,
                            headers={"Content-Type": "application/json"},
                            method="POST"
                        )
                        def _sync_post():
                            try:
                                with urllib.request.urlopen(req, timeout=0.5) as resp:
                                    pass
                            except Exception:
                                pass
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, _sync_post)
                    except Exception:
                        pass

                asyncio.create_task(_post_event_bg(event.model_dump(mode="json")))

                # Track previous event for call stack lineage chain
                last_event_id = event.id

                # Track Counts
                if risk.verdict == Verdict.ALLOWED:
                    allowed_cnt += 1
                elif risk.verdict == Verdict.QUARANTINED:
                    quarantined_cnt += 1
                    if auto_resolve_quarantine:
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

