'use client';

import React, { useState } from 'react';
import { getVerdictColor } from '../lib/colors';
import { AgentEvent } from '../types/events';

interface DrilldownProps {
  event: AgentEvent | null;
  allEvents?: AgentEvent[];
  onClose?: () => void;
  onDecideSuccess?: (eventId: string, newVerdict: 'allowed' | 'blocked') => void;
}

export default function Drilldown({
  event,
  allEvents = [],
  onClose,
  onDecideSuccess,
}: DrilldownProps) {
  const [submitting, setSubmitting] = useState(false);
  const [decideError, setDecideError] = useState<string | null>(null);
  const [decideResult, setDecideResult] = useState<string | null>(null);

  if (!event) return null;

  // Build parent causality chain
  const parentChain: AgentEvent[] = [];
  let currentParentId = event.parent_id;
  while (currentParentId) {
    const parentEvent = allEvents.find((e) => e.event_id === currentParentId);
    if (parentEvent) {
      parentChain.unshift(parentEvent);
      currentParentId = parentEvent.parent_id;
    } else {
      break;
    }
  }

  const handleDecision = async (verdict: 'allowed' | 'blocked') => {
    setSubmitting(true);
    setDecideError(null);
    setDecideResult(null);

    const apiHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
    const apiPort = process.env.NEXT_PUBLIC_API_PORT || '7777';

    try {
      const response = await fetch(`http://${apiHost}:${apiPort}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_id: event.event_id,
          verdict: verdict,
          note: `Resolved by Dashboard operator to ${verdict}`,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || `Server returned ${response.status}`);
      }

      const resData = await response.json();
      setDecideResult(`Decision submitted: ${resData.verdict}`);
      onDecideSuccess?.(event.event_id, verdict);
    } catch (err: any) {
      setDecideError(err.message || 'Failed to submit decision to server');
    } finally {
      setSubmitting(false);
    }
  };

  const verdictColor = getVerdictColor(event.verdict);

  return (
    <div className="fixed inset-y-0 right-0 w-[450px] max-w-full glass-panel border-l border-surface-border z-50 flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-surface-border bg-surface/70">
        <div className="flex items-center space-x-2">
          <span
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: verdictColor }}
          ></span>
          <h2 className="text-sm font-semibold font-mono text-slate-100 uppercase tracking-wide">
            INSPECTION DRILLDOWN
          </h2>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white p-1 rounded-md hover:bg-surface-border transition-colors font-mono text-xs"
        >
          ✕ CLOSE
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs font-mono">
        {/* Interactive Decision Control Box (If Quarantined) */}
        {event.verdict === 'quarantined' && (
          <div className="p-4 rounded-xl border border-amber-500/40 bg-amber-950/30 space-y-3">
            <div className="flex items-center space-x-2 text-amber-400 font-bold">
              <span className="animate-ping w-2 h-2 rounded-full bg-amber-400"></span>
              <span>ACTION QUARANTINED — PENDING APPROVAL</span>
            </div>
            <p className="text-slate-300 text-[11px]">
              This operation is currently held in memory. Select an override action to resolve the pending execution:
            </p>
            {decideError && (
              <div className="text-rose-400 bg-rose-950/50 p-2 rounded border border-rose-800 text-[11px]">
                {decideError}
              </div>
            )}
            {decideResult && (
              <div className="text-emerald-400 bg-emerald-950/50 p-2 rounded border border-emerald-800 text-[11px]">
                {decideResult}
              </div>
            )}
            <div className="flex items-center space-x-3 pt-1">
              <button
                disabled={submitting}
                onClick={() => handleDecision('allowed')}
                className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold rounded-lg shadow-md transition-all text-center"
              >
                {submitting ? 'Submitting...' : '✓ APPROVE ACTION'}
              </button>
              <button
                disabled={submitting}
                onClick={() => handleDecision('blocked')}
                className="flex-1 py-2 px-3 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-bold rounded-lg shadow-md transition-all text-center"
              >
                {submitting ? 'Submitting...' : '✕ BLOCK ACTION'}
              </button>
            </div>
          </div>
        )}

        {/* Overview Details */}
        <div className="space-y-2 bg-surface/40 p-3 rounded-lg border border-surface-border">
          <div className="text-slate-400 text-[10px] uppercase font-bold text-indigo-400">
            EVENT IDENTITY
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div>
              <span className="text-slate-500">Event ID:</span>
              <div className="text-slate-200 truncate">{event.event_id}</div>
            </div>
            <div>
              <span className="text-slate-500">Session ID:</span>
              <div className="text-slate-200 truncate">{event.session_id}</div>
            </div>
            <div>
              <span className="text-slate-500">Agent Persona:</span>
              <div className="text-purple-300 font-bold">{event.agent_id}</div>
            </div>
            <div>
              <span className="text-slate-500">Verdict:</span>
              <div className="font-bold uppercase" style={{ color: verdictColor }}>
                {event.verdict}
              </div>
            </div>
          </div>
        </div>

        {/* Parent Lineage / Call Stack */}
        <div className="space-y-2 bg-surface/40 p-3 rounded-lg border border-surface-border">
          <div className="text-slate-400 text-[10px] uppercase font-bold text-indigo-400">
            CALL STACK LINEAGE ({parentChain.length} Parents)
          </div>
          {parentChain.length === 0 ? (
            <div className="text-slate-500 text-[11px]">Root execution event (no parent)</div>
          ) : (
            <div className="space-y-1.5 pt-1">
              {parentChain.map((p, idx) => (
                <div
                  key={p.event_id}
                  className="flex items-center space-x-2 text-[11px] text-slate-300"
                >
                  <span className="text-slate-500 font-mono">#{idx + 1}</span>
                  <span className="text-cyan-400">{p.agent_id}</span>
                  <span className="text-slate-500">→</span>
                  <span className="truncate text-slate-200">
                    {p.tool_name || p.command || p.event_type}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Command & Target Resource */}
        <div className="space-y-2 bg-surface/40 p-3 rounded-lg border border-surface-border">
          <div className="text-slate-400 text-[10px] uppercase font-bold text-indigo-400">
            EXECUTED PAYLOAD & TARGET
          </div>
          {event.tool_name && (
            <div>
              <span className="text-slate-500 text-[10px]">MCP Tool:</span>
              <div className="text-cyan-300 font-bold text-[12px]">{event.tool_name}</div>
            </div>
          )}
          {event.command && (
            <div>
              <span className="text-slate-500 text-[10px]">Shell Command:</span>
              <pre className="bg-background p-2 rounded border border-surface-border text-amber-300 overflow-x-auto text-[11px] mt-1">
                $ {event.command}
              </pre>
            </div>
          )}
          {event.target_resource && (
            <div className="pt-1">
              <span className="text-slate-500 text-[10px]">Target Resource:</span>
              <div className="text-slate-200 bg-background p-1.5 rounded border border-surface-border mt-0.5 truncate">
                {event.target_resource}
              </div>
            </div>
          )}
        </div>

        {/* Blast Radius */}
        {event.risk?.blast_radius && (
          <div className="space-y-2 bg-surface/40 p-3 rounded-lg border border-surface-border">
            <div className="text-slate-400 text-[10px] uppercase font-bold text-indigo-400">
              BLAST RADIUS METRICS (Score: {event.risk.blast_radius.score})
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="bg-background p-2 rounded border border-surface-border">
                <span className="text-slate-400 text-[10px]">FILES IMPACTED</span>
                <div className="text-base font-bold text-white">
                  {event.risk.blast_radius.file_count}
                </div>
              </div>
              <div className="bg-background p-2 rounded border border-surface-border">
                <span className="text-slate-400 text-[10px]">DIRS IMPACTED</span>
                <div className="text-base font-bold text-white">
                  {event.risk.blast_radius.directory_count}
                </div>
              </div>
              <div className="bg-background p-2 rounded border border-surface-border">
                <span className="text-slate-400 text-[10px]">NETWORK CALL</span>
                <div className="font-bold text-white">
                  {event.risk.blast_radius.network_call ? 'YES' : 'NO'}
                </div>
              </div>
              <div className="bg-background p-2 rounded border border-surface-border">
                <span className="text-slate-400 text-[10px]">SYS COMMAND</span>
                <div className="font-bold text-white">
                  {event.risk.blast_radius.system_command ? 'YES' : 'NO'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Policy Rationale & Rules */}
        <div className="space-y-2 bg-surface/40 p-3 rounded-lg border border-surface-border">
          <div className="text-slate-400 text-[10px] uppercase font-bold text-indigo-400">
            RISK ASSESSMENT & POLICY RULES
          </div>
          <div>
            <span className="text-slate-500 text-[10px]">Rationale:</span>
            <p className="text-slate-300 text-[11px] mt-0.5 leading-relaxed">
              {event.risk?.rationale || 'No policy rationale available.'}
            </p>
          </div>

          {event.risk?.rules_triggered?.length ? (
            <div className="pt-2">
              <span className="text-slate-500 text-[10px]">Triggered Rules:</span>
              <div className="space-y-1 mt-1">
                {event.risk.rules_triggered.map((rule) => (
                  <div
                    key={rule}
                    className="px-2 py-1 rounded bg-rose-950/40 border border-rose-800/40 text-rose-300 text-[11px] font-mono"
                  >
                    • {rule}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-emerald-400 text-[11px] pt-1">
              ✓ Clean assessment — no security policy violations detected.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
