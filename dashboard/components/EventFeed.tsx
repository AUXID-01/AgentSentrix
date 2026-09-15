'use client';

import React, { useState } from 'react';
import { getVerdictColor } from '../lib/colors';
import { AgentEvent, Verdict } from '../types/events';

interface EventFeedProps {
  events: AgentEvent[];
  selectedEventId?: string;
  onSelectEvent?: (event: AgentEvent) => void;
}

export default function EventFeed({ events, selectedEventId, onSelectEvent }: EventFeedProps) {
  const [filter, setFilter] = useState<'all' | Verdict>('all');

  const filteredEvents = events.filter((e) => {
    if (filter === 'all') return true;
    return e.verdict === filter;
  });

  return (
    <div className="flex flex-col h-full glass-panel rounded-xl overflow-hidden border border-surface-border">
      {/* Header & Filter bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-border bg-surface/50">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
          <h2 className="text-sm font-semibold text-slate-100 font-mono tracking-wide">
            LIVE TELEMETRY FEED ({filteredEvents.length})
          </h2>
        </div>
        <div className="flex items-center space-x-1 bg-background/60 p-1 rounded-lg border border-surface-border text-xs font-mono">
          {(['all', 'allowed', 'quarantined', 'blocked'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setFilter(v)}
              className={`px-2.5 py-1 rounded-md capitalize transition-colors ${
                filter === v
                  ? 'bg-indigo-600 text-white font-medium'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-surface-border/50'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Feed List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filteredEvents.length === 0 ? (
          <div className="h-40 flex items-center justify-center text-slate-500 font-mono text-xs">
            No telemetry events recorded yet.
          </div>
        ) : (
          filteredEvents.map((evt) => {
            const isSelected = evt.event_id === selectedEventId;
            const verdictColor = getVerdictColor(evt.verdict);
            const timeStr = evt.timestamp
              ? new Date(evt.timestamp).toLocaleTimeString()
              : '#';

            return (
              <div
                key={evt.event_id || evt.sequence}
                onClick={() => onSelectEvent?.(evt)}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${
                  isSelected
                    ? 'border-indigo-500 bg-indigo-950/40 shadow-lg shadow-indigo-950/30'
                    : 'border-surface-border bg-surface/30 hover:border-slate-600 hover:bg-surface/60'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center space-x-2">
                    <span
                      className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider text-white"
                      style={{ backgroundColor: verdictColor }}
                    >
                      {evt.verdict}
                    </span>
                    <span className="text-xs font-mono text-slate-300 font-medium">
                      {evt.agent_id}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-500">{timeStr}</span>
                </div>

                <div className="text-xs font-mono text-slate-200 truncate">
                  {evt.tool_name ? (
                    <span className="text-cyan-400">tool: {evt.tool_name}</span>
                  ) : evt.command ? (
                    <span className="text-amber-300">$ {evt.command}</span>
                  ) : (
                    <span>{evt.event_type}</span>
                  )}
                </div>

                {evt.target_resource && (
                  <div className="mt-1 text-[11px] font-mono text-slate-400 truncate">
                    Target: <span className="text-slate-300">{evt.target_resource}</span>
                  </div>
                )}

                <div className="mt-1.5 flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1.5 border-t border-slate-800/60">
                  <span>Risk Score: <strong className="text-white">{evt.risk?.score ?? 0}</strong></span>
                  {evt.risk?.rules_triggered?.length ? (
                    <span className="text-rose-400 font-semibold">
                      {evt.risk.rules_triggered.length} Rule(s)
                    </span>
                  ) : (
                    <span className="text-emerald-400">Passed</span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
