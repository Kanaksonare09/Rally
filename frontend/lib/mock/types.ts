export type SafetyStatus = 'safe' | 'warning' | 'critical' | 'offline';

export interface Member {
  id: string;
  name: string;
  role: 'Leader' | 'Member';
  isCurrentUser: boolean;
  online: boolean;
  status: SafetyStatus;
  lat: number;
  lng: number;
  speedKmh: number;
  headingDeg: number;
  distanceFromGroupM: number;
  lastSeen: string; // human readable, e.g. "Just now" | "2 min ago"
}

export type AlertType = 'separation' | 'route_deviation' | 'connectivity' | 'stop' | 'sos';
export type AlertStatus = 'active' | 'resolved';

export interface AlertItem {
  id: string;
  type: AlertType;
  severity: 'warning' | 'high' | 'critical' | 'info';
  status: AlertStatus;
  isRead?: boolean;
  message: string;
  detail: string;
  memberId: string | null;
  memberName: string | null;
  location: string; // human readable, e.g. "0.4km from route"
  recommendedAction: string;
  time: string; // human readable
  createdAt: number; // epoch ms, for sorting
}

export interface TripStats {
  distanceKm: number;
  durationMin: number;
  membersCount: number;
  alertsCount: number;
  startedAt: number; // epoch ms
}

export interface RiskAssessment {
  score: number; // 0-100
  level: 'LOW RISK' | 'MODERATE RISK' | 'HIGH RISK';
}

export interface RouteWaypoint {
  lat: number;
  lng: number;
}

export interface Group {
  id: string;
  name: string;
  destination: string;
  destinationLat: number;
  destinationLng: number;
  maxMembers: number;
  joinCode: string;
  createdAt: number;
  members: Member[];
  alerts: AlertItem[];
  route: RouteWaypoint[];
  trip: TripStats;
  risk: RiskAssessment;
  paused: boolean;
}

export interface CreateGroupInput {
  name: string;
  destination: string;
  maxMembers: number;
}

export interface TripEvent {
  label: string;
  time: string;
}

export interface TripSummary {
  id: string;
  groupName: string;
  destination: string;
  date: string; // human readable, e.g. "Aug 22, 2026"
  completedAt: number;
  // Nullable (not just widened for real data): the backend genuinely
  // cannot compute some of these for every trip (e.g. distance with no
  // GPS history at all) — null means "unknown", never fabricated as 0
  // (Phase 13, item 24). The mock service still always supplies concrete
  // numbers, which remain assignable to these wider types.
  distanceKm: number | null;
  durationMin: number | null;
  membersCount: number;
  alertsCount: number | null;
  routeDeviations: number | null;
  separationEvents: number | null;
  unexpectedStops: number | null;
  sosCount: number | null;
  safetyScore: number | null;
  riskLevel: RiskAssessment['level'] | null;
  route: RouteWaypoint[];
  destinationLat: number;
  destinationLng: number;
  alertPoints: { lat: number; lng: number; label: string }[];
  deviationPoint: { lat: number; lng: number } | null;
  keyEvents: TripEvent[];
  insights: string[];
}

export interface Settings {
  profile: { name: string; email: string };
  notifications: {
    alerts: boolean;
    sos: boolean;
    connectivity: boolean;
    tripSummaries: boolean;
  };
  location: {
    sharing: boolean;
    accuracy: 'high' | 'balanced' | 'low';
    backgroundTracking: 'always' | 'while_active' | 'never';
  };
  safety: {
    alertSensitivity: 'low' | 'medium' | 'high';
    separationThresholdM: number;
    routeDeviationThresholdM: number;
  };
  appearance: {
    theme: 'dark' | 'light' | 'system';
    units: 'Metric' | 'Imperial';
  };
}
