/**
 * TypeScript types mirroring the REAL FastAPI backend's Pydantic response
 * shapes exactly (field names, casing, nullability) — see backend/app/schemas/*.py
 * for the source of truth each of these corresponds to. Deliberately not
 * `any`: every field the UI reads should be caught by the compiler if the
 * backend contract ever changes.
 *
 * Zero-vs-null: a `number | null` field here means the backend explicitly
 * distinguishes "genuinely zero" from "cannot be calculated" — see the
 * backend README's Analytics section. Never coerce `null` to `0` when
 * rendering these — render "unavailable"/"N/A" instead (see
 * lib/format.ts).
 */

// ---- Auth ------------------------------------------------------------

export interface Profile {
  id: string;
  full_name: string | null;
  avatar_url: string | null;
}

export interface MeResponse {
  id: string;
  email: string | null;
  profile: Profile;
}

// ---- Groups ------------------------------------------------------------

export type GroupStatus = 'ACTIVE' | 'COMPLETED' | 'ARCHIVED';
export type MemberRole = 'LEADER' | 'MEMBER';
export type MemberStatus = 'ACTIVE' | 'LEFT' | 'REMOVED';

export interface ApiGroup {
  id: string;
  name: string;
  join_code: string;
  leader_id: string | null;
  destination_name: string | null;
  status: GroupStatus;
  created_at: string;
  updated_at: string;
}

export interface ApiGroupListItem {
  id: string;
  name: string;
  role: MemberRole;
  status: GroupStatus;
}

export interface ApiGroupMember {
  user_id: string;
  name: string | null;
  avatar_url: string | null;
  role: MemberRole;
  status: MemberStatus;
  joined_at: string;
}

// ---- Trips ------------------------------------------------------------

export type TripStatus = 'CREATED' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED';

export interface ApiTrip {
  id: string;
  group_id: string;
  status: TripStatus;
  started_by: string | null;
  started_at: string | null;
  ended_at: string | null;
  destination_name: string | null;
  distance: number | null;
  duration: number | null;
  safety_score: number | null;
  created_at: string;
}

export interface TripHistoryItem {
  trip_id: string;
  name: string | null;
  status: TripStatus;
  started_at: string | null;
  ended_at: string | null;
  member_count: number;
  distance_meters: number | null;
}

export interface TripHistoryResponse {
  items: TripHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

// ---- Locations ----------------------------------------------------------

export interface LocationCreate {
  latitude: number;
  longitude: number;
  accuracy?: number | null;
  speed?: number | null; // m/s
  heading?: number | null; // 0-360 deg
  recorded_at?: string | null;
}

export interface LocationResponse {
  id: string;
  trip_id: string;
  user_id: string;
  latitude: number;
  longitude: number;
  accuracy: number | null;
  speed: number | null;
  heading: number | null;
  recorded_at: string;
  created_at: string;
}

// ---- Routes ------------------------------------------------------------

export type RouteStatus = 'PLANNED' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED';

export interface RouteCreate {
  name?: string | null;
  origin_latitude: number;
  origin_longitude: number;
  destination_latitude: number;
  destination_longitude: number;
  /** GeoJSON order: [longitude, latitude] pairs. */
  coordinates: [number, number][];
  estimated_duration_seconds?: number | null;
}

export interface ApiRoute {
  id: string;
  trip_id: string;
  name: string | null;
  origin_latitude: number;
  origin_longitude: number;
  destination_latitude: number;
  destination_longitude: number;
  coordinates: [number, number][];
  distance_meters: number;
  estimated_duration_seconds: number | null;
  status: RouteStatus;
  created_at: string;
  updated_at: string;
}

export interface RouteMemberProgress {
  user_id: string;
  name: string | null;
  role: MemberRole;
  route_state: string | null;
  route_fraction: number | null;
  distance_traveled_meters: number | null;
  distance_remaining_meters: number | null;
  distance_from_route_meters: number | null;
  eta_seconds: number | null;
  eta_source: string | null;
  location_age_seconds: number | null;
  presence: 'ONLINE' | 'OFFLINE';
}

export interface RouteProgressResponse {
  trip_id: string;
  route_id: string;
  group_route_fraction: number | null;
  trip_arrived: boolean;
  leader: RouteMemberProgress | null;
  members: RouteMemberProgress[];
}

// ---- Intelligence --------------------------------------------------------

export type IntelligenceEventType =
  | 'FALLING_BEHIND'
  | 'GROUP_SEPARATION'
  | 'UNEXPECTED_STOP'
  | 'SPEED_ANOMALY'
  | 'ISOLATED_MEMBER'
  | 'MOVING_TOGETHER'
  | 'STOPPED'
  | 'MOVING'
  | 'ROUTE_DEVIATION';

export type IntelligenceSeverity = 'INFO' | 'WARNING' | 'CRITICAL';

export interface ApiIntelligenceEvent {
  id: string;
  trip_id: string;
  event_type: IntelligenceEventType;
  severity: IntelligenceSeverity;
  user_id: string | null;
  related_user_id: string | null;
  latitude: number | null;
  longitude: number | null;
  metadata: Record<string, unknown>;
  detected_at: string;
  resolved_at: string | null;
}

// ---- Alerts ------------------------------------------------------------

export type AlertType =
  | 'FALLING_BEHIND'
  | 'GROUP_SEPARATION'
  | 'ISOLATED_MEMBER'
  | 'UNEXPECTED_STOP'
  | 'SPEED_ANOMALY'
  | 'ROUTE_DEVIATION';

export type AlertSeverity = 'INFO' | 'WARNING' | 'CRITICAL';
export type AlertStatus = 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED';

export interface ApiAlert {
  id: string;
  trip_id: string;
  event_id: string | null;
  alert_type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  message: string;
  user_id: string | null;
  related_user_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

// ---- SOS ------------------------------------------------------------

export type SOSStatus = 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED' | 'CANCELLED';

export interface SOSCreate {
  latitude: number;
  longitude: number;
  accuracy?: number | null;
  message?: string | null;
}

export interface ApiSOSEvent {
  id: string;
  trip_id: string;
  user_id: string | null;
  latitude: number;
  longitude: number;
  accuracy: number | null;
  message: string | null;
  status: SOSStatus;
  metadata: Record<string, unknown>;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

// ---- Analytics ------------------------------------------------------------

export interface TripAnalytics {
  trip_id: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  member_count: number;
  distance_traveled_meters: number | null;
  route_available: boolean;
  planned_distance_meters: number | null;
  route_completion_percent: number | null;
  alerts_count: number;
  critical_alerts_count: number;
  sos_count: number;
  route_deviations: number;
  source: 'live' | 'snapshot';
}

export interface MemberAnalyticsItem {
  user_id: string;
  name: string | null;
  role: MemberRole;
  joined_at: string | null;
  distance_traveled_meters: number | null;
  active_duration_seconds: number | null;
  movement_duration_available: boolean;
  moving_duration_seconds: number | null;
  stopped_duration_seconds: number | null;
  route_completion_percent: number | null;
  route_deviations: number;
  alerts_received: number;
  sos_triggered: number;
}

export interface MemberAnalyticsResponse {
  trip_id: string;
  members: MemberAnalyticsItem[];
}

export interface RouteAnalytics {
  route_available: boolean;
  planned_distance_meters: number | null;
  traveled_distance_meters: number | null;
  completion_percent: number | null;
  route_deviations: number;
  resolved_deviations: number;
  active_deviations: number;
  average_distance_from_route_meters: number | null;
  maximum_distance_from_route_meters: number | null;
  arrived: boolean | null;
}

export interface SafetyAnalytics {
  alerts: { total: number; info: number; warning: number; critical: number };
  by_type: Record<string, number>;
  sos: { total: number; resolved: number; cancelled: number };
  intelligence_events: { total: number; resolved: number; active: number };
}

export interface TimelineEvent {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface TripTimeline {
  trip_id: string;
  events: TimelineEvent[];
}

export interface TripInsightsStatistics {
  distance_meters: number | null;
  duration_seconds: number | null;
  route_completion_percent: number | null;
  alerts: number;
  sos: number;
  route_deviations: number;
  member_count: number;
  active_member_count: number;
}

export interface TripInsights {
  trip_id: string;
  highlights: string[];
  statistics: TripInsightsStatistics;
}

// ---- Replay ------------------------------------------------------------

export interface ReplayMemberState {
  user_id: string;
  latitude: number;
  longitude: number;
  movement_state: string | null;
  route_progress: number | null;
}

export interface ReplayFrame {
  timestamp: string;
  members: ReplayMemberState[];
}

export interface TripReplay {
  trip_id: string;
  duration_seconds: number | null;
  total_distance_meters: number | null;
  interval_seconds: number;
  timeline: ReplayFrame[];
  events: TimelineEvent[];
}

// ---- Risk ------------------------------------------------------------

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface RiskFactor {
  type: string;
  impact: number;
  description: string;
}

export interface RiskScore {
  score: number;
  level: RiskLevel;
  factors: RiskFactor[];
}

// ---- Notifications --------------------------------------------------------

export interface ApiNotification {
  id: string;
  trip_id: string | null;
  type: string;
  title: string;
  message: string;
  severity: string;
  metadata: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: ApiNotification[];
  total: number;
  unread_count: number;
  limit: number;
  offset: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

// ---- Dashboard (the primary aggregated read) ------------------------------

export interface DashboardMember {
  user_id: string;
  name: string | null;
  movement_state: string | null;
  route_state: string | null;
  progress_percent: number | null;
  distance_from_group_center_meters: number | null;
}

export interface DashboardResponse {
  mode: 'live' | 'historical';
  trip: { id: string; name: string | null; status: TripStatus; started_at: string | null };
  route: {
    route_available: boolean;
    distance_meters: number | null;
    progress_percent: number | null;
    distance_remaining_meters: number | null;
    eta_seconds: number | null;
  };
  group: {
    member_count: number;
    online_count: number | null;
    moving_count: number | null;
    stopped_count: number | null;
  };
  safety: { active_alerts: number; critical_alerts: number; active_sos: number };
  members: DashboardMember[];
  risk: { score: number; level: RiskLevel };
  eta: {
    eta_available: boolean;
    eta_seconds: number | null;
    group_eta_available: boolean;
    group_eta_seconds: number | null;
    source: string | null;
  };
  weather: {
    weather_available: boolean;
    temperature_celsius: number | null;
    condition: string | null;
    wind_speed_mps: number | null;
    precipitation_probability_percent: number | null;
    visibility_meters: number | null;
    warnings: { type: string; severity: string; reason: string }[];
  };
  notifications: { unread_count: number };
}

// ---- Demo mode (only reachable when the backend has DEMO_MODE=true) -------

export interface DemoResetResponse {
  group_id: string;
  member_count: number;
}

export interface DemoScenarioResponse {
  scenario: string;
  trip_id: string;
  total_ticks: number;
}

export interface DemoStatusResponse {
  running: boolean;
  scenario: string | null;
  trip_id: string | null;
  tick: number | null;
  total_ticks: number | null;
  available_scenarios: string[];
}

// ---- Pagination query shape reused across list endpoints ------------------

export interface PaginationParams {
  limit?: number;
  offset?: number;
  [key: string]: unknown;
}

export interface TripHistoryQuery extends PaginationParams {
  status?: TripStatus;
  from?: string;
  to?: string;
}
