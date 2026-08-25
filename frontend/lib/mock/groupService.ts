import type { AlertItem, CreateGroupInput, Group, Member, TripSummary } from './types';
import { recordTrip } from './tripHistoryService';
import { DESTINATION, START_CENTER, jitter, buildRoute } from './geo';

/**
 * GroupService is the contract the whole app talks to. Today MockGroupService
 * backs it with localStorage + a setInterval "live" simulator. Swapping in a
 * real backend later means writing a RestGroupService (fetch/WebSocket) that
 * implements this same interface — no consuming component should need to change.
 */
export interface GroupService {
  getCurrentGroup(): Group | null;
  createGroup(input: CreateGroupInput): Promise<Group>;
  joinGroup(code: string): Promise<Group>;
  leaveGroup(): void;
  sendSOS(): Promise<void>;
  resolveAlert(alertId: string): void;
  pauseTrip(): void;
  resumeTrip(): void;
  endTrip(): Promise<TripSummary>;
  subscribe(listener: (group: Group | null) => void): () => void;
}

const STORAGE_KEY = 'rally:currentGroup';

function randomJoinCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let code = '';
  for (let i = 0; i < 5; i++) code += chars[Math.floor(Math.random() * chars.length)];
  return `RALLY-${code}`;
}

// Baseline speed/distance each named member's live simulation reverts toward.
// Keep in sync with the initial values in buildMockMembers below.
const MEMBER_BASELINE: Record<string, { speedKmh: number; distanceM: number }> = {
  aman: { speedKmh: 31, distanceM: 120 },
  priya: { speedKmh: 39, distanceM: 18 },
  arjun: { speedKmh: 22, distanceM: 320 },
};

function buildMockMembers(): Member[] {
  return [
    {
      id: 'keshav',
      name: 'Keshav',
      role: 'Leader',
      isCurrentUser: true,
      online: true,
      status: 'safe',
      lat: START_CENTER.lat,
      lng: START_CENTER.lng,
      speedKmh: 42,
      headingDeg: 38,
      distanceFromGroupM: 0,
      lastSeen: 'Just now',
    },
    {
      id: 'aman',
      name: 'Aman',
      role: 'Member',
      isCurrentUser: false,
      online: true,
      status: 'warning',
      lat: jitter(START_CENTER.lat, 0.3),
      lng: jitter(START_CENTER.lng, 0.3),
      speedKmh: 31,
      headingDeg: 44,
      distanceFromGroupM: 120,
      lastSeen: 'Just now',
    },
    {
      id: 'rahul',
      name: 'Rahul',
      role: 'Member',
      isCurrentUser: false,
      online: false,
      status: 'offline',
      lat: jitter(START_CENTER.lat, 0.4),
      lng: jitter(START_CENTER.lng, 0.4),
      speedKmh: 0,
      headingDeg: 0,
      distanceFromGroupM: 210,
      lastSeen: '2 min ago',
    },
    {
      id: 'priya',
      name: 'Priya',
      role: 'Member',
      isCurrentUser: false,
      online: true,
      status: 'safe',
      lat: jitter(START_CENTER.lat, 0.25),
      lng: jitter(START_CENTER.lng, 0.25),
      speedKmh: 39,
      headingDeg: 40,
      distanceFromGroupM: 18,
      lastSeen: 'Just now',
    },
    {
      id: 'arjun',
      name: 'Arjun',
      role: 'Member',
      isCurrentUser: false,
      online: true,
      status: 'critical',
      lat: jitter(START_CENTER.lat, 0.5),
      lng: jitter(START_CENTER.lng, 0.5),
      speedKmh: 22,
      headingDeg: 51,
      distanceFromGroupM: 320,
      lastSeen: 'Just now',
    },
  ];
}

function buildInitialAlerts(members: Member[]): AlertItem[] {
  const now = Date.now();
  const byId = (id: string) => members.find((m) => m.id === id)!;

  const alerts: AlertItem[] = [
    {
      id: 'alert-aman-behind',
      type: 'separation',
      severity: 'warning',
      status: 'active',
      message: 'Falling Behind',
      detail: `${byId('aman').name} is ${byId('aman').distanceFromGroupM}m behind the group.`,
      memberId: 'aman',
      memberName: 'Aman',
      location: `${byId('aman').distanceFromGroupM}m from group center`,
      recommendedAction: 'Ask the group to slow down and regroup.',
      time: 'Just now',
      createdAt: now,
    },
    {
      id: 'alert-rahul-deviation',
      type: 'route_deviation',
      severity: 'warning',
      status: 'active',
      message: 'Route Deviation',
      detail: `${byId('rahul').name} has moved 180m away from the planned route.`,
      memberId: 'rahul',
      memberName: 'Rahul',
      location: '180m off planned route',
      recommendedAction: 'Notify Rahul and confirm the intended route change.',
      time: '1 min ago',
      createdAt: now - 60_000,
    },
    {
      id: 'alert-priya-connectivity',
      type: 'connectivity',
      severity: 'info',
      status: 'active',
      message: 'Connectivity Loss',
      detail: `${byId('priya').name} has not sent a heartbeat for 45 seconds.`,
      memberId: 'priya',
      memberName: 'Priya',
      location: 'Last known: near group center',
      recommendedAction: 'Attempt to reconnect; ask nearby members to check in.',
      time: '2 min ago',
      createdAt: now - 120_000,
    },
    {
      id: 'alert-arjun-stop',
      type: 'stop',
      severity: 'critical',
      status: 'active',
      message: 'Unexpected Stop',
      detail: `${byId('arjun').name} has remained stationary for 4 minutes.`,
      memberId: 'arjun',
      memberName: 'Arjun',
      location: `${byId('arjun').distanceFromGroupM}m from group center`,
      recommendedAction: 'Check in with Arjun to confirm status.',
      time: '4 min ago',
      createdAt: now - 240_000,
    },
  ];

  return alerts;
}

function buildTripStats(membersCount: number, alertsCount: number): Group['trip'] {
  return {
    distanceKm: 18.7,
    durationMin: 134,
    membersCount,
    alertsCount,
    startedAt: Date.now() - 42 * 60_000, // trip already in progress, matches the "Started 42 minutes ago" example
  };
}

function computeRisk(members: Member[]): Group['risk'] {
  const critical = members.filter((m) => m.status === 'critical').length;
  const warning = members.filter((m) => m.status === 'warning').length;
  const offline = members.filter((m) => m.status === 'offline').length;
  const score = Math.max(0, Math.min(100, 100 - critical * 20 - warning * 8 - offline * 5));
  const level = score >= 70 ? 'LOW RISK' : score >= 40 ? 'MODERATE RISK' : 'HIGH RISK';
  return { score, level };
}

class MockGroupService implements GroupService {
  private group: Group | null = null;
  private listeners = new Set<(group: Group | null) => void>();
  private simulationHandle: ReturnType<typeof setInterval> | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        try {
          this.group = JSON.parse(raw) as Group;
        } catch {
          this.group = null;
        }
      }
      if (this.group) this.startSimulation();
    }
  }

  getCurrentGroup(): Group | null {
    return this.group;
  }

  async createGroup(input: CreateGroupInput): Promise<Group> {
    await delay(500);

    const members = buildMockMembers();
    const group: Group = {
      id: `group-${Date.now()}`,
      name: input.name,
      destination: input.destination,
      destinationLat: DESTINATION.lat,
      destinationLng: DESTINATION.lng,
      maxMembers: input.maxMembers,
      joinCode: randomJoinCode(),
      createdAt: Date.now(),
      members,
      alerts: buildInitialAlerts(members),
      route: buildRoute(),
      trip: buildTripStats(members.length, 4),
      risk: { score: 87, level: 'LOW RISK' },
      paused: false,
    };

    this.setGroup(group);
    this.startSimulation();
    return group;
  }

  async joinGroup(rawCode: string): Promise<Group> {
    await delay(700);

    const code = rawCode.trim().toUpperCase();
    const wellFormed = /^RALLY-[A-Z0-9]{5}$/.test(code);
    if (!wellFormed) {
      throw new Error('That code doesn’t look right. Double-check it and try again.');
    }

    // If we already have a locally-created group with this exact code, join that one.
    if (this.group && this.group.joinCode === code) {
      this.startSimulation();
      return this.group;
    }

    // Otherwise simulate discovering a group on the server.
    const members = buildMockMembers();
    const group: Group = {
      id: `group-${Date.now()}`,
      name: 'Manali Adventure',
      destination: DESTINATION.name,
      destinationLat: DESTINATION.lat,
      destinationLng: DESTINATION.lng,
      maxMembers: 8,
      joinCode: code,
      createdAt: Date.now(),
      members,
      alerts: buildInitialAlerts(members),
      route: buildRoute(),
      trip: buildTripStats(members.length, 4),
      risk: { score: 87, level: 'LOW RISK' },
      paused: false,
    };

    this.setGroup(group);
    this.startSimulation();
    return group;
  }

  leaveGroup(): void {
    this.stopSimulation();
    this.group = null;
    if (typeof window !== 'undefined') window.localStorage.removeItem(STORAGE_KEY);
    this.emit();
  }

  async sendSOS(): Promise<void> {
    await delay(400);
    if (!this.group) return;
    const me = this.group.members.find((m) => m.isCurrentUser);
    const alert: AlertItem = {
      id: `alert-sos-${Date.now()}`,
      type: 'sos',
      severity: 'critical',
      status: 'active',
      message: 'SOS sent',
      detail: 'Your location was shared with all group members.',
      memberId: me?.id ?? null,
      memberName: me?.name ?? 'You',
      location: 'Current location',
      recommendedAction: 'Group members have been notified — wait for a response or call for outside help if needed.',
      time: 'Just now',
      createdAt: Date.now(),
    };
    this.group = {
      ...this.group,
      alerts: [alert, ...this.group.alerts],
      trip: { ...this.group.trip, alertsCount: this.group.trip.alertsCount + 1 },
    };
    this.persist();
    this.emit();
  }

  resolveAlert(alertId: string): void {
    if (!this.group) return;
    const alerts = this.group.alerts.map((a) => (a.id === alertId ? { ...a, status: 'resolved' as const } : a));
    this.group = { ...this.group, alerts };
    this.persist();
    this.emit();
  }

  pauseTrip(): void {
    if (!this.group) return;
    this.group = { ...this.group, paused: true };
    this.persist();
    this.emit();
  }

  resumeTrip(): void {
    if (!this.group) return;
    this.group = { ...this.group, paused: false };
    this.persist();
    this.emit();
  }

  async endTrip(): Promise<TripSummary> {
    await delay(500);
    if (!this.group) throw new Error('No active trip to end.');
    const summary = recordTrip(this.group);
    this.leaveGroup();
    return summary;
  }

  subscribe(listener: (group: Group | null) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private setGroup(group: Group) {
    this.group = group;
    this.persist();
    this.emit();
  }

  private persist() {
    if (typeof window === 'undefined' || !this.group) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(this.group));
  }

  private emit() {
    this.listeners.forEach((listener) => listener(this.group));
  }

  private startSimulation() {
    if (this.simulationHandle || typeof window === 'undefined') return;
    this.simulationHandle = setInterval(() => {
      if (!this.group || this.group.paused) return;
      const members = this.group.members.map((m) => {
        if (m.isCurrentUser || !m.online) return m;
        // Mean-revert toward each member's baseline instead of a free random
        // walk — a walk reflected at a 0 floor drifts upward forever, which
        // made group health only ever get worse the longer a demo session ran.
        const baseline = MEMBER_BASELINE[m.id];
        const targetSpeed = baseline?.speedKmh ?? m.speedKmh;
        const targetDistance = baseline?.distanceM ?? m.distanceFromGroupM;
        return {
          ...m,
          lat: jitter(m.lat, 0.03),
          lng: jitter(m.lng, 0.03),
          speedKmh: Math.max(0, Math.round(m.speedKmh + (targetSpeed - m.speedKmh) * 0.2 + (Math.random() - 0.5) * 4)),
          distanceFromGroupM: Math.max(
            0,
            Math.round(m.distanceFromGroupM + (targetDistance - m.distanceFromGroupM) * 0.15 + (Math.random() - 0.5) * 12)
          ),
        };
      });
      this.group = { ...this.group, members, risk: computeRisk(members) };
      this.persist();
      this.emit();
    }, 4000);
  }

  private stopSimulation() {
    if (this.simulationHandle) {
      clearInterval(this.simulationHandle);
      this.simulationHandle = null;
    }
  }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const groupService: GroupService = new MockGroupService();

/**
 * Builds a non-persisted, in-memory Group shape for the create-group page's
 * live preview panel — never touches localStorage or the real group state.
 */
export function buildPreviewGroup(input: Partial<CreateGroupInput>): Group {
  const members = buildMockMembers();
  return {
    id: 'preview',
    name: input.name?.trim() || 'Your Rally',
    destination: input.destination?.trim() || DESTINATION.name,
    destinationLat: DESTINATION.lat,
    destinationLng: DESTINATION.lng,
    maxMembers: input.maxMembers ?? 5,
    joinCode: 'RALLY-XXXXX',
    createdAt: Date.now(),
    members,
    alerts: [],
    route: buildRoute(),
    trip: buildTripStats(members.length, 0),
    risk: { score: 87, level: 'LOW RISK' },
    paused: false,
  };
}
