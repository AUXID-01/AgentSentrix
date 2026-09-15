import logging
from typing import Annotated, Dict, Any, List, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END

logger = logging.getLogger("agentsentrix.sim.langgraph")

# Define Agent State Schema for LangGraph
class AgentState(TypedDict):
    messages: List[BaseMessage]
    agent_id: str
    persona_name: str
    current_step: int
    session_id: str
    events_generated: List[Dict[str, Any]]

# Step definition contract for simulated LangGraph node tools
class SimulatedToolCall:
    def __init__(self, action_type: str, target_kind: str, target_label: str, target_path: str, payload: str):
        self.action_type = action_type
        self.target_kind = target_kind
        self.target_label = target_label
        self.target_path = target_path
        self.payload = payload

# Build LangGraph StateGraph for an Agent Persona
def build_agent_stategraph(agent_id: str, persona_name: str, steps: List[SimulatedToolCall]) -> Any:
    """Build a compiled LangGraph StateGraph workflow for an agent persona."""
    builder = StateGraph(AgentState)

    async def agent_node(state: AgentState) -> Dict[str, Any]:
        step_idx = state.get("current_step", 0)
        logger.info(f"[LangGraph Engine] Node Execution | Agent: {agent_id} ({persona_name}) | Step: #{step_idx + 1}/{len(steps)}")
        
        if step_idx < len(steps):
            step = steps[step_idx]
            msg = AIMessage(content=f"Executing tool call: {step.action_type} on {step.target_label}")
            return {
                "messages": state["messages"] + [msg],
                "current_step": step_idx + 1
            }
        return {"current_step": step_idx}

    builder.add_node("agent_reasoning", agent_node)
    builder.add_edge(START, "agent_reasoning")
    builder.add_edge("agent_reasoning", END)

    return builder.compile()
