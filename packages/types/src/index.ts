// User & Auth Types
export type UserRole = 'USER' | 'ADMIN';

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  avatar_url?: string;
  role: UserRole;
  created_at: string;
  updated_at: string;
}

export interface UserProfile {
  user_id: string;
  bio?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  default_activity: string;
  location_sharing_enabled: boolean;
  updated_at: string;
}

// Group Types
export type MemberRole = 'OWNER' | 'ADMIN' | 'MEMBER';

export interface GroupMember {
  id: string;
  group_id: string;
  user_id: string;
  user?: User;
  role: MemberRole;
  joined_at: string;
  is_active: boolean;
  latest_location?: LocationPoint;
  connectivity_state?: 'ONLINE' | 'OFFLINE' | 'DEGRADED';
}

export interface Group {
  id: string;
  name: string;
  description?: string;
  code: string;
  max_members: number;
  safe_distance_threshold_m: number;
  drifting_threshold_m: number;
  critical_separation_m: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
  members?: GroupMember[];
}

export interface GroupInvitation {
  id: string;
  group_id: string;
  created_by: string;
  invite_code: string;
  expires_at: string;
  max_uses: number;
  uses_count: number;
}

// Trip Types
export type TripStatus = 'PLANNED' | 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'CANCELLED';

export interface Trip {
  id: string;
  group_id: string;
  name: string;
  status: TripStatus;
  created_by: string;
  started_at?: string;
  ended_at?: string;
  planned_route_waypoints?: [number, number][]; // [lng, lat]
  created_at: string;
  updated_at: string;
}

// Location Types
export interface LocationPoint {
  id?: string;
  user_id: string;
  trip_id: string;
  group_id: string;
  latitude: number;
  longitude: number;
  accuracy?: number;
  speed?: number; // m/s
  heading?: number; // 0-360 deg
  altitude?: number;
  battery_level?: number; // 0-1
  connectivity_state?: 'ONLINE' | 'OFFLINE' | 'DEGRADED';
  device_timestamp: string;
  server_timestamp?: string;
  is_offline_synced?: boolean;
}

// Intelligence, Risk & Alerts
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type AlertType = 'DRIFTING' | 'SEPARATION' | 'ROUTE_DEVIATION' | 'UNEXPECTED_STOP' | 'CONNECTIVITY_LOSS' | 'SOS';
export type AlertSeverity = 'INFO' | 'WARNING' | 'DANGER' | 'CRITICAL';

export interface Alert {
  id: string;
  trip_id: string;
  group_id: string;
  target_user_id: string;
  target_user_name?: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  title: string;
  message: string;
  metadata?: Record<string, any>;
  is_resolved: boolean;
  created_at: string;
}

export interface Recommendation {
  id: string;
  trip_id: string;
  group_id: string;
  trigger_alert_id?: string;
  action_text: string;
  reason: string;
  priority: number;
  is_acknowledged: boolean;
  created_at: string;
}

export interface GroupHealthAssessment {
  trip_id: string;
  group_id: string;
  health_score: number; // 0-100
  risk_level: RiskLevel;
  status_label: 'OPTIMAL' | 'STABLE' | 'MODERATE_RISK' | 'HIGH_RISK' | 'CRITICAL_ALERT';
  reasons: string[];
  active_member_count: number;
  drifting_member_ids: string[];
  separated_member_ids: string[];
  created_at: string;
}

export interface SOSAlert {
  id: string;
  trip_id: string;
  group_id: string;
  user_id: string;
  user_name?: string;
  latitude: number;
  longitude: number;
  status: 'ACTIVE' | 'RESOLVED' | 'CANCELLED';
  created_at: string;
}

// WebSocket Event Wrapper
export interface RealtimeEvent<T = any> {
  event_type:
    | 'location.updated'
    | 'member.drifting'
    | 'group.separation'
    | 'route.deviation'
    | 'unexpected.stop'
    | 'connectivity.changed'
    | 'risk.updated'
    | 'recommendation.created'
    | 'sos.created'
    | 'member.joined'
    | 'member.left'
    | 'trip.started'
    | 'trip.ended';
  trip_id: string;
  group_id: string;
  sender_id: string;
  timestamp: string;
  data: T;
}
