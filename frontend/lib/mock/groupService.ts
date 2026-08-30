import type { AlertItem, CreateGroupInput, Group, Member, TripSummary } from './types';
import { recordTrip } from './tripHistoryService';
import { DESTINATION, buildRoute } from './geo';
import { fetchApi } from '../services/api';
import { supabase } from '../supabase';

export interface GroupService {
  getCurrentGroup(): Group | null;
  createGroup(input: CreateGroupInput): Promise<Group>;
  joinGroup(code: string): Promise<Group>;
  leaveGroup(): void;
  removeMember(memberId: string): Promise<void>;
  sendSOS(): Promise<void>;
  resolveAlert(alertId: string): void;
  markAlertAsRead(alertId: string): void;
  markAllAlertsAsRead(): void;
  pauseTrip(): void;
  resumeTrip(): void;
  endTrip(): Promise<TripSummary>;
  setTripRoute(destination: string, destLat: number, destLng: number, route: {lat: number, lng: number}[], distanceMeters: number, durationSeconds: number): void;
  startTrip(): void;
  subscribe(listener: (group: Group | null) => void): () => void;
  updateMyPosition(lat: number, lng: number, speed: number | null, heading: number | null): void;
}

const STORAGE_KEY = 'rally:realGroup';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

class RestGroupService implements GroupService {
  private group: Group | null = null;
  private listeners = new Set<(group: Group | null) => void>();
  private ws: WebSocket | null = null;
  private currentUserId: string | null = null;

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
      
      // Initialize connection and fetch user ID
      supabase.auth.getUser().then(({ data }) => {
        if (data.user) {
          this.currentUserId = data.user.id;
        }
        if (this.group) {
          this.connectWebSocket(this.group.id);
        }
      });
    }
  }

  getCurrentGroup(): Group | null {
    return this.group;
  }

  private async fetchFullGroupState(groupId: string): Promise<Group> {
    const [groupData, membersData, tripsData] = await Promise.all([
      fetchApi(`/groups/${groupId}`),
      fetchApi(`/groups/${groupId}/members`),
      fetchApi(`/groups/${groupId}/trips`).catch(() => []),
    ]);

    const activeTrip = tripsData.find((t: any) => t.status === 'ACTIVE');

    const members: Member[] = membersData.map((m: any) => ({
      id: m.user_id,
      name: m.name || 'Unknown',
      role: m.role === 'LEADER' ? 'Leader' : 'Member',
      isCurrentUser: m.user_id === this.currentUserId,
      online: true,
      status: 'safe',
      lat: 0,
      lng: 0,
      speedKmh: 0,
      headingDeg: 0,
      distanceFromGroupM: 0,
      lastSeen: 'Just now',
    }));

    return {
      id: groupData.id,
      name: groupData.name,
      destination: groupData.destination_name || 'Destination',
      destinationLat: 0, // Would parse from WKT if available
      destinationLng: 0,
      maxMembers: 10,
      joinCode: groupData.join_code,
      createdAt: Date.now(),
      members,
      alerts: [],
      route: buildRoute(),
      trip: {
        distanceKm: 0,
        durationMin: 0,
        membersCount: members.length,
        alertsCount: 0,
        startedAt: activeTrip ? new Date(activeTrip.started_at).getTime() : Date.now(),
      },
      risk: { score: 100, level: 'LOW RISK' },
      paused: false,
    };
  }

  async createGroup(input: CreateGroupInput): Promise<Group> {
    const { data } = await supabase.auth.getUser();
    if (data.user) this.currentUserId = data.user.id;

    const res = await fetchApi('/groups', {
      method: 'POST',
      body: JSON.stringify({
        name: input.name,
        destination_name: input.destination,
      })
    });

    const fullGroup = await this.fetchFullGroupState(res.id);
    this.setGroup(fullGroup);
    this.connectWebSocket(fullGroup.id);
    return fullGroup;
  }

  async joinGroup(rawCode: string): Promise<Group> {
    const { data } = await supabase.auth.getUser();
    if (data.user) this.currentUserId = data.user.id;
    
    const code = rawCode.trim().toUpperCase();
    
    // Join via API
    const res = await fetchApi('/groups/join', {
      method: 'POST',
      body: JSON.stringify({ join_code: code })
    });

    const fullGroup = await this.fetchFullGroupState(res.id);
    this.setGroup(fullGroup);
    this.connectWebSocket(fullGroup.id);
    return fullGroup;
  }

  async removeMember(memberId: string): Promise<void> {
    if (!this.group) return;
    this.group = {
      ...this.group,
      members: this.group.members.filter(m => m.id !== memberId)
    };
    this.persist();
    this.emit();
  }

  leaveGroup(): void {
    if (this.group) {
      // Fire and forget backend call
      fetchApi(`/groups/${this.group.id}/leave`, { method: 'POST' }).catch(console.error);
    }
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.group = null;
    if (typeof window !== 'undefined') window.localStorage.removeItem(STORAGE_KEY);
    this.emit();
  }

  private async connectWebSocket(groupId: string) {
    if (this.ws) {
      this.ws.close();
    }
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) return;

    this.ws = new WebSocket(`${WS_URL}/groups/${groupId}?token=${token}`);
    
    this.ws.onmessage = (event) => {
      if (!this.group) return;
      
      try {
        const msg = JSON.parse(event.data);
        const newGroup = { ...this.group };
        let changed = false;

        if (msg.type === 'group_state') {
          // Initialize members with live state
          const liveMembers = msg.data.members;
          newGroup.members = newGroup.members.map(m => {
            const live = liveMembers.find((lm: any) => lm.user_id === m.id);
            if (live) {
              return {
                ...m,
                lat: live.latitude || m.lat,
                lng: live.longitude || m.lng,
                speedKmh: live.speed || m.speedKmh,
                headingDeg: live.heading || m.headingDeg,
                online: live.connection_state === 'ONLINE',
              };
            }
            return m;
          });
          changed = true;
        } else if (msg.type === 'member_status') {
          newGroup.members = newGroup.members.map(m => 
            m.id === msg.data.user_id ? { ...m, online: msg.data.status === 'ONLINE' } : m
          );
          changed = true;
        } else if (msg.type === 'location_update') {
          const loc = msg.data;
          newGroup.members = newGroup.members.map(m => 
            m.id === loc.user_id ? {
              ...m,
              lat: loc.latitude,
              lng: loc.longitude,
              speedKmh: loc.speed || 0,
              headingDeg: loc.heading || 0,
              online: true
            } : m
          );
          changed = true;
        }

        if (changed) {
          this.setGroup(newGroup);
        }

      } catch (e) {
        console.error("WebSocket message parse error", e);
      }
    };
  }

  // Called by React hook when real GPS position changes
  updateMyPosition(lat: number, lng: number, speed: number | null, heading: number | null): void {
    // Update local state immediately so the map renders the marker
    if (this.group && this.currentUserId) {
      const updatedMembers = this.group.members.map(m =>
        m.id === this.currentUserId
          ? { ...m, lat, lng, speedKmh: speed ? speed * 3.6 : 0, headingDeg: heading ?? 0 }
          : m
      );
      this.group = { ...this.group, members: updatedMembers };
      this.emit();
    }

    // Also broadcast to other members via WebSocket
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.group && this.currentUserId) {
      this.ws.send(JSON.stringify({
        type: "location_update",
        data: {
          latitude: lat,
          longitude: lng,
          speed: speed ?? 0,
          heading: heading ?? 0,
        }
      }));
    }
  }

  async sendSOS(): Promise<void> {
    if (!this.group) return;
    // Real implementation would hit an endpoint
  }

  resolveAlert(alertId: string): void {
    if (!this.group) return;
    const alerts = this.group.alerts.map((a) => (a.id === alertId ? { ...a, status: 'resolved' as const } : a));
    this.group = { ...this.group, alerts };
    this.persist();
    this.emit();
  }

  markAlertAsRead(alertId: string): void {
    if (!this.group) return;
    const alerts = this.group.alerts.map((a) => (a.id === alertId ? { ...a, isRead: true } : a));
    this.group = { ...this.group, alerts };
    this.persist();
    this.emit();
  }

  markAllAlertsAsRead(): void {
    if (!this.group) return;
    const alerts = this.group.alerts.map((a) => ({ ...a, isRead: true }));
    this.group = { ...this.group, alerts };
    this.persist();
    this.emit();
  }

  pauseTrip(): void { }
  resumeTrip(): void { }
  
  setTripRoute(destination: string, destLat: number, destLng: number, route: {lat: number, lng: number}[], distanceMeters: number, durationSeconds: number): void {
    if (!this.group) return;
    this.group.destination = destination;
    this.group.destinationLat = destLat;
    this.group.destinationLng = destLng;
    this.group.route = route;
    if (!this.group.trip) {
      this.group.trip = { distanceKm: 0, durationMin: 0, membersCount: this.group.members.length, alertsCount: 0, startedAt: Date.now() };
    }
    this.group.trip.distanceKm = Number((distanceMeters / 1000).toFixed(1));
    this.group.trip.durationMin = Math.round(durationSeconds / 60);
    this.persist();
    this.emit();
  }

  startTrip(): void {
    // In mock, starting trip might just set a flag if there was one, but right now the route is sufficient
    this.emit();
  }

  async endTrip(): Promise<TripSummary> {
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
}

export const groupService: GroupService = new RestGroupService();

export function buildPreviewGroup(input: Partial<CreateGroupInput>): Group {
  return {
    id: 'preview',
    name: input.name?.trim() || 'Your Rally',
    destination: input.destination?.trim() || DESTINATION.name,
    destinationLat: DESTINATION.lat,
    destinationLng: DESTINATION.lng,
    maxMembers: input.maxMembers ?? 5,
    joinCode: 'RALLY-XXXXX',
    createdAt: Date.now(),
    members: [],
    alerts: [],
    route: buildRoute(),
    trip: { distanceKm: 0, durationMin: 0, membersCount: 1, alertsCount: 0, startedAt: Date.now() },
    risk: { score: 100, level: 'LOW RISK' },
    paused: false,
  };
}
