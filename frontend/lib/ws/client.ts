'use client';

import { env } from '@/lib/env';
import type { ClientLocationUpdateMessage, ClientMessage, ConnectionStatus, ServerMessage } from './types';

/**
 * Connects to the backend's live-tracking socket
 * (`WS /api/v1/ws/trips/{trip_id}?token=<supabase_access_token>`),
 * authenticating with the SAME Supabase access token every REST call
 * uses — no separate WebSocket auth scheme (Phase 13, item 12).
 *
 * Reconnect: bounded exponential backoff (1s, 2s, 4s, 8s, capped at
 * MAX_BACKOFF_MS), reset to the base delay after a successful connection.
 * Never retries after a clean, intentional close (trip_ended, or the
 * caller calling .disconnect()).
 */

const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 16000;
const HEARTBEAT_INTERVAL_MS = 25000;

type Listener = (message: ServerMessage) => void;
type StatusListener = (status: ConnectionStatus) => void;

export class TripSocket {
  private tripId: string;
  private getToken: () => Promise<string | null>;
  private ws: WebSocket | null = null;
  private status: ConnectionStatus = 'DISCONNECTED';
  private listeners = new Set<Listener>();
  private statusListeners = new Set<StatusListener>();
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private intentionallyClosed = false;

  constructor(tripId: string, getToken: () => Promise<string | null>) {
    this.tripId = tripId;
    this.getToken = getToken;
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  onMessage(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  onStatusChange(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }

  async connect(): Promise<void> {
    this.intentionallyClosed = false;
    await this.open();
  }

  disconnect(): void {
    this.intentionallyClosed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.stopHeartbeat();
    this.ws?.close(1000, 'client disconnect');
    this.ws = null;
    this.setStatus('DISCONNECTED');
  }

  sendLocationUpdate(data: ClientLocationUpdateMessage['data']): void {
    this.send({ type: 'location_update', data });
  }

  private send(message: ClientMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private async open(): Promise<void> {
    this.setStatus(this.reconnectAttempt > 0 ? 'RECONNECTING' : 'CONNECTING');

    const token = await this.getToken();
    if (!token) {
      // No session — nothing to authenticate the socket with. Don't spin
      // retrying; the caller's own auth flow (redirect to login on a
      // failed REST call) is what should resolve this, not this socket.
      this.setStatus('ERROR');
      return;
    }

    const url = `${env.wsUrl}/api/v1/ws/trips/${this.tripId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.reconnectAttempt = 0;
      this.setStatus('CONNECTED');
      this.startHeartbeat();
    };

    ws.onmessage = (event) => {
      let message: ServerMessage;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type === 'trip_ended') {
        this.intentionallyClosed = true; // the trip is over — no point reconnecting
      }
      this.listeners.forEach((listener) => listener(message));
    };

    ws.onerror = () => {
      this.setStatus('ERROR');
    };

    ws.onclose = () => {
      this.stopHeartbeat();
      if (this.intentionallyClosed) {
        this.setStatus('DISCONNECTED');
        return;
      }
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    this.setStatus('RECONNECTING');
    const delay = Math.min(BASE_BACKOFF_MS * 2 ** this.reconnectAttempt, MAX_BACKOFF_MS);
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      if (!this.intentionallyClosed) void this.open();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => this.send({ type: 'heartbeat' }), HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.statusListeners.forEach((listener) => listener(status));
  }
}
