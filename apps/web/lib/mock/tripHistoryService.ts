import type { Group, TripSummary } from './types';
import { DESTINATION, buildRoute } from './geo';

const HISTORY_KEY = 'rally:tripHistory';

function readRaw(): TripSummary[] | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as TripSummary[]) : null;
  } catch {
    return null;
  }
}

function write(history: TripSummary[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function demoSummary(): TripSummary {
  const route = buildRoute();
  return {
    id: 'demo-manali-aug22',
    groupName: 'Manali Adventure',
    destination: DESTINATION.name,
    date: 'Aug 22, 2026',
    completedAt: new Date('2026-08-22T18:30:00').getTime(),
    distanceKm: 18.7,
    durationMin: 134,
    membersCount: 6,
    alertsCount: 4,
    routeDeviations: 1,
    separationEvents: 2,
    unexpectedStops: 7,
    sosCount: 0,
    safetyScore: 87,
    riskLevel: 'LOW RISK',
    route,
    destinationLat: DESTINATION.lat,
    destinationLng: DESTINATION.lng,
    alertPoints: [
      { lat: route[2].lat, lng: route[2].lng, label: 'Aman fell behind' },
      { lat: route[4].lat, lng: route[4].lng, label: 'Route deviation' },
    ],
    deviationPoint: { lat: route[4].lat, lng: route[4].lng },
    keyEvents: [
      { label: 'Trip started', time: '00:00' },
      { label: 'First checkpoint reached', time: '00:32' },
      { label: 'Aman slowed down', time: '01:05' },
      { label: 'Route deviation detected', time: '01:22' },
      { label: 'Group regrouped', time: '01:48' },
      { label: 'Destination reached', time: '02:14' },
    ],
    insights: [
      'Your group remained together for most of the journey.',
      'Aman was separated from the group once.',
      'One route deviation was detected.',
    ],
  };
}

function readHistory(): TripSummary[] {
  const existing = readRaw();
  if (existing) return existing;
  const seeded = [demoSummary()];
  write(seeded);
  return seeded;
}

export function getTripHistory(): TripSummary[] {
  return readHistory().sort((a, b) => b.completedAt - a.completedAt);
}

export function getTripSummaryById(id: string): TripSummary | null {
  return readHistory().find((t) => t.id === id) ?? null;
}

export function getLatestTripSummary(): TripSummary | null {
  const history = getTripHistory();
  return history[0] ?? null;
}

/** Builds a TripSummary from the group as it stood right when the trip ended, and records it to history. */
export function recordTrip(group: Group): TripSummary {
  const elapsedMin = Math.max(1, Math.round((Date.now() - group.trip.startedAt) / 60_000));
  const byType = (type: string) => group.alerts.filter((a) => a.type === type);
  const memberLookup = (id: string | null) => group.members.find((m) => m.id === id) ?? null;

  const deviationAlert = byType('route_deviation')[0];
  const deviationMember = deviationAlert ? memberLookup(deviationAlert.memberId) : null;

  const summary: TripSummary = {
    id: `trip-${Date.now()}`,
    groupName: group.name,
    destination: group.destination,
    date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
    completedAt: Date.now(),
    distanceKm: group.trip.distanceKm,
    durationMin: elapsedMin,
    membersCount: group.members.length,
    alertsCount: group.alerts.length,
    routeDeviations: byType('route_deviation').length,
    separationEvents: byType('separation').length,
    unexpectedStops: byType('stop').length,
    sosCount: byType('sos').length,
    safetyScore: group.risk.score,
    riskLevel: group.risk.level,
    route: group.route,
    destinationLat: group.destinationLat,
    destinationLng: group.destinationLng,
    alertPoints: group.alerts
      .map((a) => {
        const m = memberLookup(a.memberId);
        return m ? { lat: m.lat, lng: m.lng, label: a.message } : null;
      })
      .filter((p): p is { lat: number; lng: number; label: string } => p !== null),
    deviationPoint: deviationMember ? { lat: deviationMember.lat, lng: deviationMember.lng } : null,
    keyEvents: [
      { label: 'Trip started', time: '00:00' },
      { label: 'First checkpoint reached', time: '00:30' },
      ...(byType('separation').length > 0 ? [{ label: 'Member slowed down', time: '01:00' }] : []),
      ...(byType('route_deviation').length > 0 ? [{ label: 'Route deviation detected', time: '01:20' }] : []),
      { label: 'Group regrouped', time: '01:45' },
      { label: 'Trip ended', time: `${String(Math.floor(elapsedMin / 60)).padStart(2, '0')}:${String(elapsedMin % 60).padStart(2, '0')}` },
    ],
    insights: [
      byType('separation').length > 0
        ? `Your group remained mostly together, with ${byType('separation').length} separation event${byType('separation').length > 1 ? 's' : ''}.`
        : 'Your group remained together for the entire journey.',
      ...(deviationMember ? [`${deviationMember.name} was separated from the route once.`] : []),
      ...(byType('route_deviation').length > 0 ? ['One route deviation was detected.'] : []),
    ],
  };

  const history = readHistory();
  write([summary, ...history]);
  return summary;
}
