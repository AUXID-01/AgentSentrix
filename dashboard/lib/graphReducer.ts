import { AgentEvent, GraphLink, GraphNode, GraphSnapshot } from '../types/events';

export interface GraphState {
  nodes: GraphNode[];
  links: GraphLink[];
}

export type GraphAction =
  | { type: 'SET_SNAPSHOT'; payload: GraphSnapshot }
  | { type: 'ADD_EVENT'; payload: AgentEvent }
  | { type: 'UPDATE_VERDICT'; payload: { event_id: string; verdict: 'allowed' | 'blocked' | 'quarantined' } }
  | { type: 'CLEAR_GRAPH' };

export const initialGraphState: GraphState = {
  nodes: [],
  links: [],
};

export function graphReducer(state: GraphState, action: GraphAction): GraphState {
  switch (action.type) {
    case 'SET_SNAPSHOT': {
      const { nodes, links } = action.payload;
      return {
        nodes: [...nodes],
        links: [...links],
      };
    }

    case 'UPDATE_VERDICT': {
      const { event_id, verdict } = action.payload;
      const updatedNodes = state.nodes.map((n) =>
        n.id === event_id || n.event_id === event_id ? { ...n, verdict } : n
      );
      const updatedLinks = state.links.map((l) => {
        const srcId = typeof l.source === 'object' ? l.source.id : l.source;
        const tgtId = typeof l.target === 'object' ? l.target.id : l.target;
        if (tgtId === event_id || srcId === event_id) {
          return { ...l, verdict };
        }
        return l;
      });
      return { nodes: updatedNodes, links: updatedLinks };
    }

    case 'ADD_EVENT': {
      const event = action.payload;
      const nodesMap = new Map<string, GraphNode>(state.nodes.map((n) => [n.id, n]));
      const linksSet = new Set<string>(
        state.links.map((l) => {
          const src = typeof l.source === 'object' ? l.source.id : l.source;
          const tgt = typeof l.target === 'object' ? l.target.id : l.target;
          return `${src}->${tgt}`;
        })
      );

      // 1. Ensure Agent Node exists
      if (!nodesMap.has(event.agent_id)) {
        nodesMap.set(event.agent_id, {
          id: event.agent_id,
          label: `Agent: ${event.agent_id}`,
          node_type: 'agent',
          verdict: 'allowed',
          risk_score: 0,
          agent_id: event.agent_id,
        });
      }

      // 2. Action Node
      const actionLabel = event.tool_name
        ? `${event.tool_name}`
        : event.command
        ? `$ ${event.command.slice(0, 20)}`
        : event.event_type;

      nodesMap.set(event.event_id, {
        id: event.event_id,
        label: actionLabel,
        node_type: 'action',
        verdict: event.verdict,
        risk_score: event.risk ? event.risk.score : 0,
        agent_id: event.agent_id,
        event_id: event.event_id,
      });

      const newLinks: GraphLink[] = [...state.links];

      // 3. Parent Link or Agent Link
      const parentSourceId =
        event.parent_id && nodesMap.has(event.parent_id) ? event.parent_id : event.agent_id;

      const linkKey = `${parentSourceId}->${event.event_id}`;
      if (!linksSet.has(linkKey)) {
        linksSet.add(linkKey);
        newLinks.push({
          source: parentSourceId,
          target: event.event_id,
          relationship: event.parent_id ? 'spawned' : 'executed',
          verdict: event.verdict,
        });
      }

      // 4. Resource Node & Link
      if (event.target_resource) {
        const resId = `res_${event.target_resource}`;
        if (!nodesMap.has(resId)) {
          nodesMap.set(resId, {
            id: resId,
            label: event.target_resource,
            node_type: 'resource',
            verdict: event.verdict,
            risk_score: event.risk ? event.risk.score : 0,
            agent_id: event.agent_id,
            event_id: event.event_id,
          });
        }

        const resLinkKey = `${event.event_id}->${resId}`;
        if (!linksSet.has(resLinkKey)) {
          linksSet.add(resLinkKey);
          newLinks.push({
            source: event.event_id,
            target: resId,
            relationship: 'targeted',
            verdict: event.verdict,
          });
        }
      }

      return {
        nodes: Array.from(nodesMap.values()),
        links: newLinks,
      };
    }

    case 'CLEAR_GRAPH':
      return { nodes: [], links: [] };

    default:
      return state;
  }
}
