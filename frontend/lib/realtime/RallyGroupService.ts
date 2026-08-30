'use client';

/**
 * RallyGroupService — a REAL, backend-backed implementation of the exact
 * same `GroupService` interface `lib/mock/groupService.ts` defined (see
 * that file's own docstring: "Swapping in a real backend later means
 * writing a RestGroupService... no consuming component should need to
 * change"). This is that swap. Every existing page/component that
 * imports `groupService`/`useGroup` keeps working against the same
 * `Group`/`Member`/`AlertItem`/`TripStats`/`RiskAssessment` shapes —
 * only the data source changes, from localStorage+setInterval to real
 * REST + WebSocket.
 *
 * Data model reconciliation: the existing UI treats "a group" and "its
 * one live trip" as one merged concept. The real backend correctly keeps
 * them separate (Phase 3 Groups vs Phase 4 Trips vs Phase 9 Routes) — a
 * group can exist with no trip, or a trip that hasn't started yet. This
 * service bridges that gap explicitly: `getCurrentGroup()` returns
 * non-null only once the caller's group has a trip in CREATED or ACTIVE
 * state (i.e. "there's a Rally in progress to show"), matching the
 * existing empty-state UX in components/dashboard/RequireGroup.tsx.
 *
 * Live member positions come from the WebSocket (`trip_state` on
 * connect, then `location_update`/`presence_update` incrementally) —
 * the REST dashboard response deliberately doesn't carry raw lat/lng
 * (see backend/app/schemas/analytics.py's DashboardMember), only
 * movement_state/route_state/progress. This service merges both: the
 * dashboard call for safety/risk/eta/weather/notifications/route
 * aggregates, the socket for actual positions — exactly the "HTTP =
 * initial state, WebSocket = live updates" split Phase 13 calls for.
 */

import { getCurrentAccessToken } from '@/lib/auth/AuthProvider';
import { getMe } from '@/lib/api/auth';
import * as alertsApi from '@/lib/api/alerts';
import * as analyticsApi from '@/lib/api/analytics';
import * as groupsApi from '@/lib/api/groups';
import * as routesApi from '@/lib/api/routes';
import * as sosApi from '@/lib/api/sos';
import * as tripsApi from '@/lib/api/trips';
import { ApiError } from '@/lib/api/errors';
import type { ApiAlert, ApiGroup, ApiGroupMember, ApiTrip, DashboardResponse } from '@/lib/api/types';
import { TripSocket } from '@/lib/ws/client';
import type { ConnectionStatus, ServerMessage, TripStateMember } from '@/lib/ws/types';
import type { AlertItem, AlertType as MockAlertType, CreateGroupInput, Group, Member, RiskAssessment, SafetyStatus, TripSummary } from '@/lib/mock/types';
import type { GroupService } from '@/lib/mock/groupService';

const REFRESH_INTERVAL_MS = 20_000;

const ALERT_TYPE_MAP: Record<string, MockAlertType> = {
  FALLING_BEHIND: 'separation',
  GROUP_SEPARATION: 'separation',
  ISOLATED_MEMBER: 'separation',
  ROUTE_DEVIATION: 'route_deviation',
  UNEXPECTED_STOP: 'stop',
  SPEED_ANOMALY: 'stop',
};

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return 'Never';
  const diffSec = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (diffSec < 10) return 'Just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  return `${Math.round(diffMin / 60)}h ago`;
}

function riskLevelFromBackend(level: string): RiskAssessment['level'] {
  // The backend has 4 bands (LOW/MEDIUM/HIGH/CRITICAL); the existing UI
  // only ever had 3 (RiskRing, TripSummary). CRITICAL folds into the
  // same 'HIGH RISK' bucket the UI already renders as its most severe
  // state, rather than adding a fourth color the design never accounted
  // for — the `score` itself still reflects the true 0-100 value either way.
  if (level === 'LOW') return 'LOW RISK';
  if (level === 'MEDIUM') return 'MODERATE RISK';
  return 'HIGH RISK';
}

class RallyGroupService implements GroupService {
  private group: Group | null = null;
  private listeners = new Set<(group: Group | null) => void>();

  private apiGroup: ApiGroup | null = null;
  private apiTrip: ApiTrip | null = null;
  private currentUserId: string | null = null;

  private livePositions = new Map<string, TripStateMember>();
  private activeAlerts: ApiAlert[] = [];
  private lastDashboard: DashboardResponse | null = null;

  private socket: TripSocket | null = null;
  private refreshTimer: ReturnType<typeof setInterval> | null = null;
  private initPromise: Promise<void> | null = null;

  // Real WebSocket connection state (Phase 13, items 12-14) — surfaced
  // via useConnectionStatus() so the UI can show CONNECTED/CONNECTING/
  // RECONNECTING/ERROR instead of a hardcoded "Connected" label.
  private connectionStatus: ConnectionStatus = 'DISCONNECTED';
  private connectionListeners = new Set<(status: ConnectionStatus) => void>();

  // ---- GroupService interface --------------------------------------

  getCurrentGroup(): Group | null {
    return this.group;
  }

  async createGroup(input: CreateGroupInput): Promise<Group> {
    const apiGroup = await groupsApi.createGroup({ name: input.name, destination_name: input.destination });
    let trip = await tripsApi.createTrip(apiGroup.id, { destination_name: input.destination });
    try {
      // The creator is about to lead the trip right away — matches the
      // existing UX, where creating a group immediately shows a live
      // dashboard. The backend still makes the actual CREATED -> ACTIVE
      // decision; if it refuses (e.g. a genuine business-rule conflict),
      // the group is still returned, just not yet "live".
      trip = await tripsApi.startTrip(trip.id);
    } catch {
      // Left in CREATED state — attachToTrip() below reflects that honestly.
    }
    await this.attachToTrip(apiGroup, trip);
    return this.requireGroup();
  }

  async joinGroup(rawCode: string): Promise<Group> {
    const apiGroup = await groupsApi.joinGroup(rawCode.trim());
    const trip = await this.findRelevantTrip(apiGroup.id);
    if (!trip) {
      throw new Error('You joined the group, but it has no trip in progress yet.');
    }
    await this.attachToTrip(apiGroup, trip);
    return this.requireGroup();
  }

  leaveGroup(): void {
    void this.teardown();
  }

  async sendSOS(): Promise<void> {
    if (!this.apiTrip) throw new Error('No active trip.');
    const position = this.livePositions.get(this.currentUserId ?? '');
    // Never fabricate 0,0 — if we genuinely have no live fix yet, refuse
    // rather than send a meaningless location with an emergency.
    if (position?.latitude == null || position?.longitude == null) {
      throw new Error('Waiting for a GPS fix — try again in a moment.');
    }
    await sosApi.triggerSOS(this.apiTrip.id, { latitude: position.latitude, longitude: position.longitude });
    await this.refresh();
  }

  async resolveAlertAsync(alertId: string): Promise<void> {
    await alertsApi.resolveAlert(alertId);
    await this.refresh();
  }

  /** Kept synchronous to satisfy the existing GroupService interface
   * (components call this without awaiting) — fires the real request
   * and refreshes once it resolves; errors are logged, not thrown, since
   * no caller currently awaits this. Prefer resolveAlertAsync from new
   * code that can handle the error. */
  resolveAlert(alertId: string): void {
    void this.resolveAlertAsync(alertId).catch((err) => console.error('Failed to resolve alert', err));
  }

  /** No backend equivalent — Phase 4-12's trip state machine has no
   * "paused" state, only CREATED/ACTIVE/COMPLETED/CANCELLED (see
   * backend/app/services/trip_service.py). Interpreted here as a
   * client-only signal that stops sending GPS updates (see
   * lib/geo/useGeolocation.ts) without telling the backend anything —
   * the trip itself stays ACTIVE the whole time. */
  pauseTrip(): void {
    if (!this.group) return;
    this.group = { ...this.group, paused: true };
    this.emit();
  }

  resumeTrip(): void {
    if (!this.group) return;
    this.group = { ...this.group, paused: false };
    this.emit();
  }

  async endTrip(): Promise<TripSummary> {
    if (!this.apiTrip) throw new Error('No active trip to end.');
    const ended = await tripsApi.endTrip(this.apiTrip.id);
    const [analytics, insights] = await Promise.all([
      analyticsApi.getTripAnalytics(ended.id).catch(() => null),
      analyticsApi.getTripInsights(ended.id).catch(() => null),
    ]);
    const summary = this.buildTripSummary(ended, analytics, insights);
    await this.teardown();
    return summary;
  }

  subscribe(listener: (group: Group | null) => void): () => void {
    this.listeners.add(listener);
    if (!this.initPromise) {
      this.initPromise = this.init();
    } else {
      // A subscriber joining after the first init() already resolved
      // (e.g. a second component mounting, or navigating to a new page)
      // needs the CURRENT state right away — otherwise it sees nothing
      // until the next periodic refresh, up to REFRESH_INTERVAL_MS later.
      listener(this.group);
    }
    return () => this.listeners.delete(listener);
  }

  // ---- internal --------------------------------------------------------

  private requireGroup(): Group {
    if (!this.group) throw new Error('Group is not attached.');
    return this.group;
  }

  private async init(): Promise<void> {
    const token = await getCurrentAccessToken();
    if (!token) {
      this.emit();
      return;
    }
    try {
      const groups = await groupsApi.listMyGroups();
      for (const g of groups) {
        const trip = await this.findRelevantTrip(g.id);
        if (trip) {
          const fullGroup = await groupsApi.getGroup(g.id);
          await this.attachToTrip(fullGroup, trip);
          return;
        }
      }
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        console.error('Failed to load current group', err);
      }
    }
    this.emit();
  }

  private async findRelevantTrip(groupId: string): Promise<ApiTrip | null> {
    const history = await tripsApi.listGroupTripHistory(groupId, { limit: 5 });
    const active = history.items.find((t) => t.status === 'ACTIVE');
    if (active) return tripsApi.getTrip(active.trip_id);
    const created = history.items.find((t) => t.status === 'CREATED');
    if (created) return tripsApi.getTrip(created.trip_id);
    return null;
  }

  private async attachToTrip(apiGroup: ApiGroup, trip: ApiTrip): Promise<void> {
    await this.teardownSocketAndTimer();
    this.apiGroup = apiGroup;
    this.apiTrip = trip;
    this.livePositions.clear();

    const token = await getCurrentAccessToken();
    if (token) {
      try {
        const me = await getMe();
        this.currentUserId = me.id;
      } catch {
        this.currentUserId = null;
      }
    }

    await this.refresh();

    if (trip.status === 'ACTIVE') {
      this.socket = new TripSocket(trip.id, getCurrentAccessToken);
      this.socket.onMessage((message) => this.handleSocketMessage(message));
      this.socket.onStatusChange((status) => {
        this.setConnectionStatus(status);
        if (status === 'CONNECTED') void this.refresh(); // re-sync after (re)connect — item 37
      });
      void this.socket.connect();
    } else {
      this.setConnectionStatus('DISCONNECTED');
    }

    this.refreshTimer = setInterval(() => void this.refresh(), REFRESH_INTERVAL_MS);
  }

  private handleSocketMessage(message: ServerMessage): void {
    switch (message.type) {
      case 'trip_state':
        for (const member of message.data.members) this.livePositions.set(member.user_id, member);
        this.rebuildGroup();
        break;
      case 'location_update': {
        const existing = this.livePositions.get(message.data.user_id);
        this.livePositions.set(message.data.user_id, {
          user_id: message.data.user_id,
          name: existing?.name ?? null,
          role: existing?.role ?? 'MEMBER',
          latitude: message.data.latitude,
          longitude: message.data.longitude,
          accuracy: message.data.accuracy,
          speed: message.data.speed,
          heading: message.data.heading,
          recorded_at: message.data.recorded_at,
          status: 'ONLINE',
        });
        this.rebuildGroup();
        break;
      }
      case 'presence_update': {
        const existing = this.livePositions.get(message.data.user_id);
        if (existing) this.livePositions.set(message.data.user_id, { ...existing, status: message.data.status });
        this.rebuildGroup();
        break;
      }
      case 'alert':
      case 'alert_updated':
      case 'sos':
      case 'sos_updated':
      case 'intelligence_event':
      case 'route_progress':
      case 'route_deviation':
        // These change safety/risk/route aggregates in ways only the
        // dashboard endpoint can recompute correctly — refetch rather
        // than trying to reconstruct backend-side logic client-side.
        void this.refresh();
        break;
      case 'trip_ended':
        void this.refresh();
        break;
      default:
        break;
    }
  }

  private async refresh(): Promise<void> {
    if (!this.apiGroup || !this.apiTrip) return;
    try {
      const [dashboard, members, alerts] = await Promise.all([
        analyticsApi.getDashboard(this.apiTrip.id),
        groupsApi.getGroupMembers(this.apiGroup.id),
        alertsApi.listActiveTripAlerts(this.apiTrip.id).catch(() => [] as ApiAlert[]),
      ]);
      this.lastDashboard = dashboard;
      this.activeAlerts = alerts;
      this.apiTrip = { ...this.apiTrip, status: dashboard.trip.status };
      this.rebuildGroup(members);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return; // client.ts already redirects
      console.error('Failed to refresh dashboard', err);
    }
  }

  private rebuildGroup(memberList?: ApiGroupMember[]): void {
    if (!this.apiGroup || !this.apiTrip || !this.lastDashboard) return;

    const dashboard = this.lastDashboard;
    const dashboardByUser = new Map(dashboard.members.map((m) => [m.user_id, m]));
    const alertsByUser = new Map<string, ApiAlert>();
    for (const alert of this.activeAlerts) {
      if (alert.user_id && (!alertsByUser.has(alert.user_id) || alert.severity === 'CRITICAL')) {
        alertsByUser.set(alert.user_id, alert);
      }
    }

    const roster = memberList ?? this.group?.members.map((m) => ({ user_id: m.id, name: m.name, avatar_url: null, role: m.role.toUpperCase() as 'LEADER' | 'MEMBER', status: 'ACTIVE' as const, joined_at: '' })) ?? [];

    const members: Member[] = roster.map((m) => {
      const live = this.livePositions.get(m.user_id);
      const dashboardEntry = dashboardByUser.get(m.user_id);
      const alert = alertsByUser.get(m.user_id);
      const online = live?.status === 'ONLINE';

      const status: SafetyStatus = !online
        ? 'offline'
        : alert?.severity === 'CRITICAL'
          ? 'critical'
          : alert
            ? 'warning'
            : 'safe';

      return {
        id: m.user_id,
        name: m.name ?? 'Member',
        role: m.role === 'LEADER' ? 'Leader' : 'Member',
        isCurrentUser: m.user_id === this.currentUserId,
        online,
        status,
        lat: live?.latitude ?? 0,
        lng: live?.longitude ?? 0,
        speedKmh: live?.speed != null ? Math.round(live.speed * 3.6) : 0,
        headingDeg: live?.heading ?? 0,
        distanceFromGroupM: dashboardEntry?.distance_from_group_center_meters != null ? Math.round(dashboardEntry.distance_from_group_center_meters) : 0,
        lastSeen: relativeTime(live?.recorded_at),
      };
    });

    const alerts: AlertItem[] = this.activeAlerts.map((a) => {
      const member = members.find((m) => m.id === a.user_id);
      return {
        id: a.id,
        type: ALERT_TYPE_MAP[a.alert_type] ?? 'stop',
        severity: a.severity === 'CRITICAL' ? 'critical' : a.severity === 'WARNING' ? 'warning' : 'info',
        status: a.status === 'RESOLVED' ? 'resolved' : 'active',
        message: a.title,
        detail: a.message,
        memberId: a.user_id,
        memberName: member?.name ?? null,
        location: member ? `${member.distanceFromGroupM}m from group center` : '',
        recommendedAction: 'Review this alert and check in with the affected member.',
        time: relativeTime(a.created_at),
        createdAt: new Date(a.created_at).getTime(),
      };
    });

    const startedAt = this.apiTrip.started_at ? new Date(this.apiTrip.started_at).getTime() : Date.now();

    this.group = {
      id: this.apiGroup.id,
      name: this.apiGroup.name,
      destination: this.apiGroup.destination_name ?? this.apiTrip.destination_name ?? 'Destination',
      destinationLat: 0,
      destinationLng: 0,
      maxMembers: Math.max(members.length, 5),
      joinCode: this.apiGroup.join_code,
      createdAt: new Date(this.apiGroup.created_at).getTime(),
      members,
      alerts,
      route: [],
      trip: {
        distanceKm: dashboard.route.distance_meters != null ? dashboard.route.distance_meters / 1000 : 0,
        durationMin: Math.max(0, Math.round((Date.now() - startedAt) / 60_000)),
        membersCount: members.length,
        alertsCount: alerts.length,
        startedAt,
      },
      risk: { score: dashboard.risk.score, level: riskLevelFromBackend(dashboard.risk.level) },
      paused: this.group?.paused ?? false,
    };

    this.emit();
    void this.loadRouteGeometry();
  }

  private routeLoadedForTrip: string | null = null;
  private async loadRouteGeometry(): Promise<void> {
    if (!this.apiTrip || !this.group) return;
    if (this.routeLoadedForTrip === this.apiTrip.id) return;
    try {
      const route = await routesApi.getRoute(this.apiTrip.id);
      this.routeLoadedForTrip = this.apiTrip.id;
      if (!this.group) return;
      this.group = {
        ...this.group,
        route: route.coordinates.map(([lon, lat]) => ({ lat, lng: lon })),
        destinationLat: route.destination_latitude,
        destinationLng: route.destination_longitude,
      };
      this.emit();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        this.routeLoadedForTrip = this.apiTrip.id; // no route on this trip — stop asking every refresh
      }
    }
  }

  private buildTripSummary(trip: ApiTrip, analytics: Awaited<ReturnType<typeof analyticsApi.getTripAnalytics>> | null, insights: Awaited<ReturnType<typeof analyticsApi.getTripInsights>> | null): TripSummary {
    const group = this.group;
    // this.activeAlerts only ever holds ACTIVE alerts (see refresh()), so
    // it undercounts separation/stop events for a trip that's ending —
    // resolved ones already dropped out of it. Analytics doesn't break
    // those two counts out individually, so this is a known approximation
    // (documented as a Known Issue), not a silent fabrication: it's real
    // alerts that were seen, just possibly not the full historical set.
    const safetyByType = (type: string) => this.activeAlerts.filter((a) => a.alert_type === type).length;
    return {
      id: trip.id,
      groupName: group?.name ?? 'Rally',
      destination: group?.destination ?? trip.destination_name ?? 'Destination',
      date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
      completedAt: Date.now(),
      distanceKm: analytics?.distance_traveled_meters != null ? analytics.distance_traveled_meters / 1000 : null,
      durationMin: analytics?.duration_seconds != null ? Math.round(analytics.duration_seconds / 60) : null,
      membersCount: analytics?.member_count ?? group?.members.length ?? 0,
      alertsCount: analytics?.alerts_count ?? null,
      routeDeviations: analytics?.route_deviations ?? null,
      separationEvents: safetyByType('GROUP_SEPARATION') + safetyByType('FALLING_BEHIND'),
      unexpectedStops: safetyByType('UNEXPECTED_STOP'),
      sosCount: analytics?.sos_count ?? null,
      safetyScore: group?.risk.score ?? null,
      riskLevel: group?.risk.level ?? null,
      route: group?.route ?? [],
      destinationLat: group?.destinationLat ?? 0,
      destinationLng: group?.destinationLng ?? 0,
      alertPoints: [],
      deviationPoint: null,
      keyEvents: [],
      insights: insights?.highlights ?? [],
    };
  }

  private async teardownSocketAndTimer(): Promise<void> {
    this.socket?.disconnect();
    this.socket = null;
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    this.refreshTimer = null;
    this.setConnectionStatus('DISCONNECTED');
  }

  private setConnectionStatus(status: ConnectionStatus): void {
    this.connectionStatus = status;
    this.connectionListeners.forEach((listener) => listener(status));
  }

  private async teardown(): Promise<void> {
    await this.teardownSocketAndTimer();
    this.apiGroup = null;
    this.apiTrip = null;
    this.livePositions.clear();
    this.activeAlerts = [];
    this.lastDashboard = null;
    this.routeLoadedForTrip = null;
    this.group = null;
    this.emit();
  }

  private emit(): void {
    this.listeners.forEach((listener) => listener(this.group));
  }

  /** Sends one GPS fix over the live-tracking socket — the browser
   * geolocation hook's send path (see lib/geo/useTripLocationSharing.ts).
   * A no-op if there's no open socket (trip not ACTIVE, or "paused" —
   * see pauseTrip()'s docstring) rather than falling back to a REST
   * call, which would defeat the point of throttling client-side. */
  sendLocationUpdate(data: { latitude: number; longitude: number; accuracy: number | null; speed: number | null; heading: number | null }): void {
    if (this.group?.paused) return;
    this.socket?.sendLocationUpdate(data);
  }

  /** The most recent dashboard response backing the current `group` —
   * kept in sync with it (refreshed just before rebuildGroup() runs), so
   * pages that need route/eta/weather/notifications detail beyond the
   * mock `Group` shape can read it without issuing a second, duplicate
   * fetch (Phase 13, item 25/46). Null until the first refresh lands. */
  getLastDashboard(): DashboardResponse | null {
    return this.lastDashboard;
  }

  /** The real backend trip id behind the current group, for pages that
   * need to call trip-scoped endpoints directly (route progress, replay,
   * analytics detail) that the shared `Group` shape doesn't carry. */
  getTripId(): string | null {
    return this.apiTrip?.id ?? null;
  }

  getConnectionStatus(): ConnectionStatus {
    return this.connectionStatus;
  }

  /** Fires immediately with the current status, then on every change —
   * so a component mounting after the socket already connected doesn't
   * have to wait for the next transition to know where things stand. */
  subscribeConnectionStatus(listener: (status: ConnectionStatus) => void): () => void {
    this.connectionListeners.add(listener);
    listener(this.connectionStatus);
    return () => this.connectionListeners.delete(listener);
  }
}

const rallyGroupServiceInstance = new RallyGroupService();
export const rallyGroupService: GroupService = rallyGroupServiceInstance;
/** Escape hatch for the one capability (sending GPS) that isn't part of
 * the shared GroupService interface the mock implementation also
 * satisfies — see lib/geo/useTripLocationSharing.ts. */
export const rallyGroupServiceLocation = rallyGroupServiceInstance;
