import { AgentEvent, GraphSnapshot, WsEnvelope } from '../types/events';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WsClientOptions {
  url?: string;
  onEvent?: (event: AgentEvent) => void;
  onSnapshot?: (snapshot: GraphSnapshot) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
}

export class AgentSentrixWsClient {
  private ws: WebSocket | null = null;
  private baseUrl: string;
  private lastSeq: number = 0;
  private reconnectAttempt: number = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private pingInterval: NodeJS.Timeout | null = null;
  private isIntentionallyClosed: boolean = false;

  public status: ConnectionStatus = 'disconnected';
  public onEvent?: (event: AgentEvent) => void;
  public onSnapshot?: (snapshot: GraphSnapshot) => void;
  public onStatusChange?: (status: ConnectionStatus) => void;

  constructor(options: WsClientOptions = {}) {
    // Default to localhost:7777 if not specified
    this.baseUrl = options.url || 'ws://localhost:7777/ws';
    this.onEvent = options.onEvent;
    this.onSnapshot = options.onSnapshot;
    this.onStatusChange = options.onStatusChange;
  }

  public connect(): void {
    this.isIntentionallyClosed = false;
    this.setStatus('connecting');

    const connectUrl = this.lastSeq > 0 ? `${this.baseUrl}?since=${this.lastSeq}` : this.baseUrl;

    try {
      this.ws = new WebSocket(connectUrl);

      this.ws.onopen = () => {
        this.setStatus('connected');
        this.reconnectAttempt = 0;
        this.startPing();
      };

      this.ws.onmessage = (event) => {
        try {
          const envelope: WsEnvelope = JSON.parse(event.data);
          this.handleMessage(envelope);
        } catch (err) {
          console.error('[AgentSentrix WS] Error parsing message:', err);
        }
      };

      this.ws.onerror = (err) => {
        console.error('[AgentSentrix WS] Error:', err);
        this.setStatus('error');
      };

      this.ws.onclose = () => {
        this.stopPing();
        if (!this.isIntentionallyClosed) {
          this.setStatus('disconnected');
          this.scheduleReconnect();
        }
      };
    } catch (err) {
      console.error('[AgentSentrix WS] Connection exception:', err);
      this.setStatus('error');
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    this.isIntentionallyClosed = true;
    this.stopPing();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  private handleMessage(envelope: WsEnvelope): void {
    if (envelope.seq && envelope.seq > this.lastSeq) {
      this.lastSeq = envelope.seq;
    }

    if (envelope.type === 'event' && envelope.data) {
      this.onEvent?.(envelope.data as AgentEvent);
    } else if (envelope.type === 'snapshot' && envelope.data) {
      this.onSnapshot?.(envelope.data as GraphSnapshot);
    } else if (envelope.type === 'pong') {
      // Heartbeat ack
    }
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.onStatusChange?.(status);
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempt), 10000);
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startPing(): void {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 15000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}
