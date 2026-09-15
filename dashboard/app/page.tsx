'use client';

import React, { useEffect, useReducer, useState } from 'react';
import Drilldown from '../components/Drilldown';
import EventFeed from '../components/EventFeed';
import RiskGauge from '../components/RiskGauge';
import ThreatCanvas from '../components/ThreatCanvas';
import { graphReducer, initialGraphState } from '../lib/graphReducer';
import { normalizeEvent } from '../lib/normalizeEvent';
import { AgentSentrixWsClient, ConnectionStatus } from '../lib/ws';
import { AgentEvent, GraphNode } from '../types/events';

interface SystemLog {
  id: string;
  time: string;
  level: 'info' | 'warn' | 'error' | 'success';
  msg: string;
}

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

  const [systemLogs, setSystemLogs] = useState<SystemLog[]>([]);

  const addLog = (level: 'info' | 'warn' | 'error' | 'success', msg: string) => {
    const time = new Date().toLocaleTimeString();
    const id = Math.random().toString(36).substring(2, 9);
    setSystemLogs((prev) => [{ id, time, level, msg }, ...prev.slice(0, 49)]);
  };

  useEffect(() => {
    const apiHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
    const apiPort = process.env.NEXT_PUBLIC_API_PORT || '7777';

    addLog('info', `Connecting to AgentSentrix API Gateway (http://${apiHost}:${apiPort})...`);

    // 1. Initial REST fetch for current graph snapshot, health & event history
    fetch(`http://${apiHost}:${apiPort}/graph`)
      .then((res) => (res.ok ? res.json() : null))
      .then((snapshot) => {
        if (snapshot) {
          dispatchGraph({ type: 'SET_SNAPSHOT', payload: snapshot });
          addLog('info', `Topology snapshot loaded (${snapshot.nodes?.length || 0} nodes, ${snapshot.links?.length || 0} links)`);
        }
      })
      .catch((err) => {
        addLog('warn', `Server /graph offline: ${err.message || err}`);
      });

    fetch(`http://${apiHost}:${apiPort}/health`)
      .then((res) => (res.ok ? res.json() : null))
      .then((health) => {
        setServerHealth(health);
        if (health) {
          addLog('success', `Health check OK — Redis: ${health.redis ? 'ONLINE' : 'OFFLINE'}, DuckDB: ${health.duckdb ? 'ONLINE' : 'OFFLINE'}`);
        }
      })
      .catch(() => {
        setServerHealth(null);
        addLog('error', 'Backend server unreachable on port 7777.');
      });

    fetch(`http://${apiHost}:${apiPort}/events?limit=50`)
      .then((res) => (res.ok ? res.json() : null))
      .then((resData) => {
        if (resData && Array.isArray(resData.events) && resData.events.length > 0) {
          const normalized = resData.events.map((e: any) => normalizeEvent(e));
          setEvents(normalized);
          addLog('info', `Fetched ${normalized.length} historical events from DuckDB analytics storage.`);
        }
      })
      .catch(() => {});

    // Periodic health poll every 3 seconds
    const healthInterval = setInterval(() => {
      fetch(`http://${apiHost}:${apiPort}/health`)
        .then((res) => (res.ok ? res.json() : null))
        .then((health) => setServerHealth(health))
        .catch(() => setServerHealth(null));
    }, 3000);

    // 2. Connect WebSocket
    const client = new AgentSentrixWsClient({
      url: `ws://${apiHost}:${apiPort}/ws`,
      onEvent: (rawEvent) => {
        const normEvt = normalizeEvent(rawEvent);
        setEvents((prev) => [normEvt, ...prev]);
        dispatchGraph({ type: 'ADD_EVENT', payload: normEvt });

        const logLvl = normEvt.verdict === 'blocked' ? 'error' : normEvt.verdict === 'quarantined' ? 'warn' : 'info';
        addLog(logLvl, `[${normEvt.verdict.toUpperCase()}] ${normEvt.agent_id} → ${normEvt.tool_name || normEvt.command || normEvt.event_type} (Risk: ${normEvt.risk.score})`);
      },
      onSnapshot: (snapshot) => {
        dispatchGraph({ type: 'SET_SNAPSHOT', payload: snapshot });
      },
      onStatusChange: (status) => {
        setWsStatus(status);
        if (status === 'connected') {
          addLog('success', 'WebSocket real-time telemetry stream CONNECTED.');
        } else if (status === 'disconnected') {
          addLog('warn', 'WebSocket disconnected. Retrying...');
        }
      },
    });

    client.connect();

    return () => {
      clearInterval(healthInterval);
      client.disconnect();
    };
  }, []);

  const handleSelectNode = (node: GraphNode) => {
    const targetEvent = events.find(
      (e) => e.event_id === node.id || e.event_id === node.event_id
    );

    if (targetEvent) {
      setSelectedEvent(targetEvent);
    } else {
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
    addLog('success', `Quarantine action '${eventId}' resolved to ${newVerdict.toUpperCase()} by operator.`);
  };

  return (
    <main className="flex flex-col h-screen w-screen bg-background overflow-hidden p-4 space-y-4">
      {/* Top Navbar */}
      <header className="glass-panel rounded-xl px-6 py-3 flex items-center justify-between border border-surface-border shrink-0">
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
              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                serverHealth?.redis
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  : 'bg-rose-950 text-rose-400 border border-rose-800'
              }`}
            >
              REDIS: {serverHealth?.redis ? 'OK' : 'OFFLINE'}
            </span>
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
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
        {/* Left Column: 3D Threat Canvas + System Execution Console (8 cols) */}
        <section className="col-span-8 flex flex-col h-full min-h-0 space-y-3">
          <div className="flex-1 min-h-0 relative">
            <ThreatCanvas
              nodes={graphState.nodes}
              links={graphState.links}
              onSelectNode={handleSelectNode}
            />
          </div>

          {/* System Execution Log Console Terminal Box */}
          <div className="h-48 shrink-0 glass-panel rounded-xl border border-surface-border bg-slate-950/90 p-3.5 flex flex-col overflow-hidden font-mono text-xs shadow-xl">
            <div className="flex items-center justify-between pb-2 mb-1.5 border-b border-slate-800 text-[10px] text-slate-400 font-bold uppercase tracking-wider shrink-0">
              <span className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                <span>SYSTEM EXECUTION LOG CONSOLE</span>
              </span>
              <div className="flex items-center space-x-3 text-[10px]">
                <span>{systemLogs.length} LOGS RECORDED</span>
                {systemLogs.length > 0 && (
                  <button
                    onClick={() => setSystemLogs([])}
                    className="text-slate-500 hover:text-slate-300 transition-colors uppercase tracking-wider font-bold"
                  >
                    [CLEAR LOGS]
                  </button>
                )}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto pr-1 space-y-1 text-[11px] font-mono scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
              {systemLogs.length === 0 ? (
                <div className="text-slate-600 text-[10px] italic py-2">
                  System log console active — waiting for telemetry events...
                </div>
              ) : (
                systemLogs.map((log) => {
                  const colorClass =
                    log.level === 'error'
                      ? 'text-rose-400 font-semibold'
                      : log.level === 'warn'
                      ? 'text-amber-400'
                      : log.level === 'success'
                      ? 'text-emerald-400'
                      : 'text-slate-300';
                  return (
                    <div key={log.id} className="flex items-start space-x-2 hover:bg-slate-900/50 p-0.5 rounded transition-colors">
                      <span className="text-slate-500 text-[10px] shrink-0">[{log.time}]</span>
                      <span className={`${colorClass} break-all font-mono leading-tight`}>{log.msg}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
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

