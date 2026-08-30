/**
 * Builds the mock-shaped `TripSummary` for a SPECIFIC (usually already-
 * completed) trip, purely from real backend data — used by the trip
 * summary page when it's opened with a trip id (from history, or right
 * after ending a trip). Mirrors what RallyGroupService.buildTripSummary
 * does for the trip a live session just ended, but works for any trip id
 * the caller has permission to view, independent of any live session
 * state (Phase 13, item 29/30).
 */

import { getTrip } from '@/lib/api/trips';
import { getGroup } from '@/lib/api/groups';
import { getTripAnalytics, getTripInsights, getTripRisk, getTripTimeline } from '@/lib/api/analytics';
import { getRoute } from '@/lib/api/routes';
import { ApiError } from '@/lib/api/errors';
import type { RiskAssessment, TripEvent, TripSummary } from '@/lib/mock/types';
import type { RiskLevel, TimelineEvent } from '@/lib/api/types';

function riskLevelFromBackend(level: RiskLevel): RiskAssessment['level'] {
  if (level === 'LOW') return 'LOW RISK';
  if (level === 'MEDIUM') return 'MODERATE RISK';
  return 'HIGH RISK';
}

function humanizeEventType(type: string): string {
  return type
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function toTripEvent(event: TimelineEvent): TripEvent {
  const label =
    typeof event.data?.title === 'string'
      ? event.data.title
      : typeof event.data?.message === 'string'
        ? event.data.message
        : humanizeEventType(event.type);
  return {
    label,
    time: new Date(event.timestamp).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
  };
}

export async function fetchTripSummary(tripId: string): Promise<TripSummary> {
  const trip = await getTrip(tripId);

  const [group, analytics, insights, timeline, route, risk] = await Promise.all([
    getGroup(trip.group_id).catch(() => null),
    getTripAnalytics(tripId).catch(() => null),
    getTripInsights(tripId).catch(() => null),
    getTripTimeline(tripId).catch(() => null),
    getRoute(tripId).catch((err) => {
      if (err instanceof ApiError && err.status === 404) return null;
      throw err;
    }),
    getTripRisk(tripId).catch(() => null),
  ]);

  // getTripInsights doesn't carry a risk score directly — the dashboard
  // endpoint (live mode) is where that lives, and it's not meaningful to
  // call for a trip that's already over. Insights' own statistics are
  // the honest source for a completed trip's numbers.
  const stats = insights?.statistics ?? null;

  const dateSource = trip.ended_at ?? trip.started_at ?? trip.created_at;

  return {
    id: trip.id,
    groupName: group?.name ?? 'Rally',
    destination: group?.destination_name ?? trip.destination_name ?? 'Destination',
    date: new Date(dateSource).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
    completedAt: trip.ended_at ? new Date(trip.ended_at).getTime() : Date.now(),
    distanceKm: (stats?.distance_meters ?? analytics?.distance_traveled_meters) != null
      ? (stats?.distance_meters ?? analytics!.distance_traveled_meters!) / 1000
      : null,
    durationMin: (stats?.duration_seconds ?? analytics?.duration_seconds) != null
      ? Math.round((stats?.duration_seconds ?? analytics!.duration_seconds!) / 60)
      : null,
    membersCount: stats?.member_count ?? analytics?.member_count ?? 0,
    alertsCount: stats?.alerts ?? analytics?.alerts_count ?? null,
    routeDeviations: stats?.route_deviations ?? analytics?.route_deviations ?? null,
    // The backend doesn't break separation/stop events out individually
    // in either analytics or insights for a completed trip — only the
    // combined alert count. Rather than guess at a split, leave both
    // null; the timeline below still shows each real event by type.
    separationEvents: null,
    unexpectedStops: null,
    sosCount: stats?.sos ?? analytics?.sos_count ?? null,
    safetyScore: risk?.score ?? null,
    riskLevel: risk ? riskLevelFromBackend(risk.level) : null,
    route: route ? route.coordinates.map(([lon, lat]) => ({ lat, lng: lon })) : [],
    destinationLat: route?.destination_latitude ?? 0,
    destinationLng: route?.destination_longitude ?? 0,
    alertPoints: [],
    deviationPoint: null,
    keyEvents: timeline?.events.map(toTripEvent) ?? [],
    insights: insights?.highlights ?? [],
  };
}
