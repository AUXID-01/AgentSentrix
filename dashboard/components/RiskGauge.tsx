'use client';

import React from 'react';
import { AgentEvent } from '../types/events';

interface RiskGaugeProps {
  events: AgentEvent[];
}

export default function RiskGauge({ events }: RiskGaugeProps) {
  const total = events.length;
  const allowed = events.filter((e) => e.verdict === 'allowed').length;
  const quarantined = events.filter((e) => e.verdict === 'quarantined').length;
  const blocked = events.filter((e) => e.verdict === 'blocked').length;

  // Calculate composite system risk score (weighted average of recent events)
  const recentEvents = events.slice(-20);
  const avgRisk =
    recentEvents.length > 0
      ? Math.round(
          recentEvents.reduce((acc, e) => acc + (e.risk?.score || 0), 0) /
            recentEvents.length
        )
      : 0;

  // Color selection based on risk level
  const gaugeColor =
    avgRisk > 70 ? '#ef4444' : avgRisk > 35 ? '#f59e0b' : '#10b981';

  // SVG Gauge calculations
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (avgRisk / 100) * circumference;

  return (
    <div className="glass-panel rounded-xl p-4 border border-surface-border flex flex-col justify-between">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider">
          COMPOSITE RISK INDEX
        </h3>
        <span
          className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase"
          style={{ backgroundColor: gaugeColor, color: '#fff' }}
        >
          {avgRisk > 70 ? 'CRITICAL' : avgRisk > 35 ? 'ELEVATED' : 'NORMAL'}
        </span>
      </div>

      <div className="flex items-center justify-around py-2">
        {/* Radial SVG Gauge */}
        <div className="relative w-28 h-28 flex items-center justify-center">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              r={radius}
              stroke="rgba(255, 255, 255, 0.08)"
              strokeWidth="10"
              fill="transparent"
            />
            <circle
              cx="50"
              cy="50"
              r={radius}
              stroke={gaugeColor}
              strokeWidth="10"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              fill="transparent"
              style={{ transition: 'stroke-dashoffset 0.5s ease' }}
            />
          </svg>
          <div className="absolute flex flex-col items-center justify-center">
            <span className="text-2xl font-bold font-mono text-white">{avgRisk}</span>
            <span className="text-[9px] font-mono text-slate-400">/ 100 RISK</span>
          </div>
        </div>

        {/* Counter Pills */}
        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          <div className="bg-surface/50 border border-surface-border p-2 rounded-lg text-center">
            <div className="text-slate-400 text-[10px]">TOTAL</div>
            <div className="text-lg font-bold text-white">{total}</div>
          </div>
          <div className="bg-emerald-950/40 border border-emerald-800/40 p-2 rounded-lg text-center">
            <div className="text-emerald-400 text-[10px]">ALLOWED</div>
            <div className="text-lg font-bold text-emerald-300">{allowed}</div>
          </div>
          <div className="bg-amber-950/40 border border-amber-800/40 p-2 rounded-lg text-center">
            <div className="text-amber-400 text-[10px]">QUARANTINE</div>
            <div className="text-lg font-bold text-amber-300">{quarantined}</div>
          </div>
          <div className="bg-rose-950/40 border border-rose-800/40 p-2 rounded-lg text-center">
            <div className="text-rose-400 text-[10px]">BLOCKED</div>
            <div className="text-lg font-bold text-rose-300">{blocked}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
