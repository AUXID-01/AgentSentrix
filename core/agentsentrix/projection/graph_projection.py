import logging
from datetime import datetime, timezone
from typing import Any
from ..schema.enums import Verdict, NodeKind
from ..schema.events import AgentEvent
from ..schema.graph import GraphNode, GraphLink, GraphSnapshot

logger = logging.getLogger("agentsentrix.projection")

def _now() -> datetime:
    return datetime.now(timezone.utc)

class GraphProjection:
    """
    Stateful graph projection transformer that converts an incoming AgentEvent stream
    into a dynamic graph topology snapshot (nodes & links).
    """

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.links: dict[str, GraphLink] = {}
        self.max_seq: int = 0

    async def consume(self, event: AgentEvent) -> None:
        """Process incoming AgentEvent and update topology projection."""
        self.max_seq = max(self.max_seq, event.seq)
        session_id = event.session_id or "default_session"

        # 1. Upsert Agent Node
        agent_node_id = f"agent:{event.agent.id}"
        if agent_node_id not in self.nodes:
            self.nodes[agent_node_id] = GraphNode(
                id=agent_node_id,
                kind=NodeKind.AGENT,
                label=event.agent.name or event.agent.id,
                max_risk=event.risk.score,
                event_count=1,
                last_seen=event.ts,
                meta={"model": event.agent.model or "unknown", "framework": event.agent.framework or "unknown"}
            )
        else:
            node = self.nodes[agent_node_id]
            node.event_count += 1
            node.max_risk = max(node.max_risk, event.risk.score)
            node.last_seen = event.ts

        # 2. Upsert Target Node
        target_node_id = event.target.node_id
        if target_node_id not in self.nodes:
            self.nodes[target_node_id] = GraphNode(
                id=target_node_id,
                kind=event.target.kind,
                label=event.target.label,
                max_risk=event.risk.score,
                event_count=1,
                last_seen=event.ts,
                meta={"path": event.target.path, "host": event.target.host}
            )
        else:
            node = self.nodes[target_node_id]
            node.event_count += 1
            node.max_risk = max(node.max_risk, event.risk.score)
            node.last_seen = event.ts

        # 3. Upsert Link (Agent -> Target)
        link_id = f"{agent_node_id}->{target_node_id}"
        if link_id not in self.links:
            self.links[link_id] = GraphLink(
                id=link_id,
                source=agent_node_id,
                target=target_node_id,
                last_verdict=event.risk.verdict,
                max_risk=event.risk.score,
                count=1,
                last_event_id=event.id,
                last_ts=event.ts
            )
        else:
            link = self.links[link_id]
            link.count += 1
            link.max_risk = max(link.max_risk, event.risk.score)
            link.last_verdict = event.risk.verdict
            link.last_event_id = event.id
            link.last_ts = event.ts

        logger.debug(f"[GraphProjection] Updated topology projection (Nodes: {len(self.nodes)}, Links: {len(self.links)})")

    def get_snapshot(self, session_id: str = "default_session") -> GraphSnapshot:
        """Return the current topology snapshot."""
        return GraphSnapshot(
            session_id=session_id,
            nodes=list(self.nodes.values()),
            links=list(self.links.values()),
            seq=self.max_seq
        )
