export type Verdict = 'allowed' | 'quarantined' | 'blocked' | 'pending';

export type EventLevel = 'info' | 'warning' | 'error' | 'critical';

export type RiskCategory =
  | 'filesystem'
  | 'exec'
  | 'network'
  | 'exfiltration'
  | 'persistence'
  | 'privilege'
  | 'unknown';

export interface BlastRadius {
  file_count: number;
  directory_count: number;
  network_call: boolean;
  system_command: boolean;
  score: number;
}

export interface RiskAssessment {
  category: RiskCategory;
  confidence: number;
  rationale: string;
  rules_triggered: string[];
  blast_radius: BlastRadius;
  score: number;
}

export interface AgentEvent {
  event_id: string;
  session_id: string;
  agent_id: string;
  parent_id: string | null;
  timestamp: string;
  event_type: string;
  tool_name: string | null;
  command: string | null;
  target_resource: string | null;
  risk: RiskAssessment;
  verdict: Verdict;
  sequence: number;
}

export interface GraphNode {
  id: string;
  label: string;
  node_type: 'agent' | 'action' | 'resource';
  verdict: Verdict;
  risk_score: number;
  agent_id: string;
  event_id?: string;
  // Three.js force graph positions (optional runtime props)
  x?: number;
  y?: number;
  z?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  relationship: string;
  verdict: Verdict;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  links: GraphLink[];
  timestamp: string;
}

export type WsMessageType = 'event' | 'snapshot' | 'ping' | 'pong';

export interface WsEnvelope {
  type: WsMessageType;
  seq?: number;
  data?: AgentEvent | GraphSnapshot;
  timestamp?: string;
}
