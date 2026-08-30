/**
 * The WebSocket wire protocol, matching backend/app/websocket/schemas.py
 * exactly — every message either direction is `{"type": "...", "data": {...}}`.
 * Only the message types the backend actually emits are declared here
 * (Phase 13, item 42 — "do not create event types the backend doesn't emit").
 */

// ---- Client -> server -------------------------------------------------

export interface ClientLocationUpdateMessage {
  type: 'location_update';
  data: {
    latitude: number;
    longitude: number;
    accuracy?: number | null;
    speed?: number | null;
    heading?: number | null;
    recorded_at?: string | null;
  };
}

export interface ClientHeartbeatMessage {
  type: 'heartbeat';
}

export type ClientMessage = ClientLocationUpdateMessage | ClientHeartbeatMessage;

// ---- Server -> client -------------------------------------------------

export interface TripStateMember {
  user_id: string;
  name: string | null;
  role: string;
  latitude: number | null;
  longitude: number | null;
  accuracy: number | null;
  speed: number | null;
  heading: number | null;
  recorded_at: string | null;
  status: 'ONLINE' | 'OFFLINE';
}

export interface ServerTripStateMessage {
  type: 'trip_state';
  data: { trip_id: string; members: TripStateMember[] };
}

export interface ServerLocationUpdateMessage {
  type: 'location_update';
  data: {
    user_id: string;
    latitude: number;
    longitude: number;
    accuracy: number | null;
    speed: number | null;
    heading: number | null;
    recorded_at: string;
    updated_at: string;
  };
}

export interface ServerLocationAckMessage {
  type: 'location_ack';
  data: { recorded_at: string; accepted: boolean };
}

export interface ServerPresenceUpdateMessage {
  type: 'presence_update';
  data: { user_id: string; status: 'ONLINE' | 'OFFLINE' };
}

export interface ServerTripEndedMessage {
  type: 'trip_ended';
  data: { trip_id: string; status: string };
}

export interface ServerHeartbeatAckMessage {
  type: 'heartbeat_ack';
  data: { server_time: string };
}

export interface ServerIntelligenceEventMessage {
  type: 'intelligence_event';
  data: {
    event_type: string;
    severity: string;
    user_id: string | null;
    related_user_id: string | null;
    detected_at: string;
    resolved_at: string | null;
    metadata: Record<string, unknown>;
  };
}

export interface ServerAlertMessage {
  type: 'alert';
  data: {
    id: string;
    alert_type: string;
    severity: string;
    title: string;
    message: string;
    user_id: string | null;
    created_at: string;
  };
}

export interface ServerAlertUpdatedMessage {
  type: 'alert_updated';
  data: { alert_id: string; status: string };
}

export interface ServerSosMessage {
  type: 'sos';
  data: {
    id: string;
    trip_id: string;
    user_id: string;
    latitude: number;
    longitude: number;
    accuracy: number | null;
    message: string | null;
    status: string;
    triggered_at: string;
  };
}

export interface ServerSosUpdatedMessage {
  type: 'sos_updated';
  data: { sos_id: string; status: string };
}

export interface ServerRouteProgressMessage {
  type: 'route_progress';
  data: {
    trip_id: string;
    route_id: string;
    group_route_fraction: number | null;
    trip_arrived: boolean;
    members: {
      user_id: string;
      route_state: string | null;
      route_fraction: number | null;
      distance_remaining_meters: number | null;
      eta_seconds: number | null;
    }[];
    server_time: string;
  };
}

export interface ServerRouteDeviationMessage {
  type: 'route_deviation';
  data: {
    user_id: string | null;
    distance_from_route_meters: number | null;
    status: 'DEVIATED' | 'BACK_ON_ROUTE';
    detected_at: string;
  };
}

export interface ServerErrorMessage {
  type: 'error';
  data: { code: string; message: string };
}

export type ServerMessage =
  | ServerTripStateMessage
  | ServerLocationUpdateMessage
  | ServerLocationAckMessage
  | ServerPresenceUpdateMessage
  | ServerTripEndedMessage
  | ServerHeartbeatAckMessage
  | ServerIntelligenceEventMessage
  | ServerAlertMessage
  | ServerAlertUpdatedMessage
  | ServerSosMessage
  | ServerSosUpdatedMessage
  | ServerRouteProgressMessage
  | ServerRouteDeviationMessage
  | ServerErrorMessage;

export type ConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'RECONNECTING' | 'ERROR';
