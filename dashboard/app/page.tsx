'use client';

import React, { useEffect, useReducer, useState } from 'react';
import Drilldown from '../components/Drilldown';
import EventFeed from '../components/EventFeed';
import RiskGauge from '../components/RiskGauge';
import ThreatCanvas from '../components/ThreatCanvas';
import { graphReducer, initialGraphState } from '../lib/graphReducer';
import { AgentSentrixWsClient, ConnectionStatus } from '../lib/ws';
import { AgentEvent, GraphNode } from '../types/events';

export default function DashboardPage() {
  const [graphState, dispatchGraph] = useReducer(graphReducer, initialGraphState);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<AgentEvent | null>(null);
  const [wsStatus, setWsStatus] = useState<ConnectionStatus>('disconnected');
  const [serverHealth, setServerHealth] = useState<{
    redis?: boolean;
    duckdb?: boolean;
    bus?: boolean;
  } | null>(null);

  useEffect(() => {
    // 1. Initial REST fetch for current graph snapshot & health
    fetch('http://localhost:8000/graph')
      .then((res) => (res.ok ? res.json() : null))
      .then((snapshot) => {
        if (snapshot) dispatchGraph({ type: 'SET_SNAPSHOT', payload: snapshot });
      })
      .catch((err) => console.log('Backend server /graph fetch error:', err));

    fetch('http://localhost:8000/health')
      .then((res) => (res.ok ? res.json() : null))
      .then((health) => setServerHealth(health))
      .catch(() => setServerHealth(null));

    // 2. Connect WebSocket
    const client = new AgentSentrixWsClient({
      url: 'ws://localhost:8000/ws',
      onEvent: (event) => {
        setEvents((prev) => [event, ...prev]);
        dispatchGraph({ type: 'ADD_EVENT', payload: event });
      },
      onSnapshot: (snapshot) => {
        dispatchGraph({ type: 'SET_SNAPSHOT', payload: snapshot });
      },
      onStatusChange: (status) => setWsStatus(status),
    });

    client.connect();

    return () => {
      client.disconnect();
    };
  }, []);

  const handleSelectNode = (node: GraphNode) => {
    // Find matching event if node has event_id
    const targetEvent = events.find(
      (e) => e.event_id === node.id || e.event_id === node.event_id
    );

    if (targetEvent) {
      setSelectedEvent(targetEvent);
    } else {
      // Create synthetic event display for node
      const dummyEvt: AgentEvent = {
        event_id: node.id,
        session_id: 'live_session',
        agent_id: node.agent_id || node.id,
        parent_id: null,
        timestamp: new Date().toISOString(),
        event_type: node.node_type,
        tool_name: node.node_type === 'action' ? node.label : null,
        command: null,
        target_resource: node.node_type === 'resource' ? node.label : null,
        risk: {
          category: 'unknown',
          confidence: 1.0,
          rationale: `Selected topology node: ${node.label}`,
          rules_triggered: [],
          blast_radius: {
            file_count: 0,
            directory_count: 0,
            network_call: false,
            system_command: false,
            score: 0,
          },
          score: node.risk_score || 0,
        },
        verdict: node.verdict || 'allowed',
        sequence: 0,
      };
      setSelectedEvent(dummyEvt);
    }
  };

  const handleDecideSuccess = (eventId: string, newVerdict: 'allowed' | 'blocked') => {
    setEvents((prev) =>
      prev.map((e) => (e.event_id === eventId ? { ...e, verdict: newVerdict } : e))
    );
    if (selectedEvent && selectedEvent.event_id === eventId) {
      setSelectedEvent({ ...selectedEvent, verdict: newVerdict });
    }
  };

  return (
    <main className="flex flex-col h-screen w-screen bg-background overflow-hidden p-4 space-y-4">
      {/* Top Navbar */}
      <header className="glass-panel rounded-xl px-6 py-3 flex items-center justify-between border border-surface-border">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center font-mono font-bold text-indigo-400">
            AS
          </div>
          <div>
            <h1 className="text-sm font-bold font-mono text-white tracking-wider flex items-center space-x-2">
              <span>AGENTSENTRIX</span>
              <span className="text-slate-500">//</span>
              <span className="text-indigo-400 font-medium">3D THREAT VISUALIZER</span>
            </h1>
            <p className="text-[10px] font-mono text-slate-400">
              REAL-TIME MULTI-AGENT INTERCEPTION & RISK ENGINE
            </p>
          </div>
        </div>

        {/* System Badges & WebSocket Status */}
        <div className="flex items-center space-x-4 text-xs font-mono">
          {/* Health Badges */}
          <div className="flex items-center space-x-2 bg-surface/60 px-3 py-1.5 rounded-lg border border-surface-border">
            <span className="text-slate-400 text-[10px]">INFRA:</span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] ${
                serverHealth?.redis
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  : 'bg-rose-950 text-rose-400 border border-rose-800'
              }`}
            >
              REDIS: {serverHealth?.redis ? 'OK' : 'OFFLINE'}
            </span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] ${
                serverHealth?.duckdb
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  : 'bg-rose-950 text-rose-400 border border-rose-800'
              }`}
            >
              DUCKDB: {serverHealth?.duckdb ? 'OK' : 'OFFLINE'}
            </span>
          </div>

          {/* WebSocket Status Indicator */}
          <div className="flex items-center space-x-2 bg-surface/60 px-3 py-1.5 rounded-lg border border-surface-border">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                wsStatus === 'connected'
                  ? 'bg-emerald-500 animate-pulse'
                  : wsStatus === 'connecting'
                  ? 'bg-amber-500 animate-ping'
                  : 'bg-rose-500'
              }`}
            ></span>
            <span className="text-slate-200 uppercase font-semibold text-[11px]">
              WS: {wsStatus}
            </span>
          </div>
        </div>
      </header>

      {/* Main Command Dashboard Layout */}
      <div className="flex-1 grid grid-cols-12 gap-4 min-h-0">
        {/* Left Column: 3D Threat Canvas (8 cols) */}
        <section className="col-span-8 h-full min-h-0 relative">
          <ThreatCanvas
            nodes={graphState.nodes}
            links={graphState.links}
            onSelectNode={handleSelectNode}
          />
        </section>

        {/* Right Column: Risk Gauge & Live Event Feed (4 cols) */}
        <section className="col-span-4 flex flex-col h-full space-y-4 min-h-0">
          <div className="h-44 shrink-0">
            <RiskGauge events={events} />
          </div>
          <div className="flex-1 min-h-0">
            <EventFeed
              events={events}
              selectedEventId={selectedEvent?.event_id}
              onSelectEvent={(evt) => setSelectedEvent(evt)}
            />
          </div>
        </section>
      </div>

      {/* Inspection Drilldown Modal Drawer Overlay */}
      {selectedEvent && (
        <Drilldown
          event={selectedEvent}
          allEvents={events}
          onClose={() => setSelectedEvent(null)}
          onDecideSuccess={handleDecideSuccess}
        />
      )}
    </main>
  );
}
