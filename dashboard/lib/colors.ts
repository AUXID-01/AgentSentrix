import { Verdict } from '../types/events';

export const VERDICT_COLORS: Record<Verdict, string> = {
  allowed: '#10b981',      // Emerald Green
  quarantined: '#f59e0b',  // Amber / Yellow
  blocked: '#ef4444',      // Rose Red
  pending: '#3b82f6',      // Sky Blue
};

export const VERDICT_GLOWS: Record<Verdict, string> = {
  allowed: 'rgba(16, 185, 129, 0.4)',
  quarantined: 'rgba(245, 158, 11, 0.4)',
  blocked: 'rgba(239, 68, 68, 0.5)',
  pending: 'rgba(59, 130, 246, 0.4)',
};

export const NODE_TYPE_COLORS = {
  agent: '#8b5cf6',     // Violet / Purple
  action: '#10b981',    // Dynamic based on verdict
  resource: '#06b6d4',  // Cyan
};

export function getVerdictColor(verdict?: Verdict | string): string {
  if (!verdict) return '#94a3b8';
  const v = verdict.toLowerCase() as Verdict;
  return VERDICT_COLORS[v] || '#94a3b8';
}

export function getVerdictGlow(verdict?: Verdict | string): string {
  if (!verdict) return 'rgba(148, 163, 184, 0.3)';
  const v = verdict.toLowerCase() as Verdict;
  return VERDICT_GLOWS[v] || 'rgba(148, 163, 184, 0.3)';
}
