import { api } from './client';
import type {
  DashboardResponse,
  MemberAnalyticsResponse,
  RouteAnalytics,
  SafetyAnalytics,
  TripAnalytics,
  TripInsights,
  TripTimeline,
} from './types';
import type { RiskScore } from './types';

export function getTripAnalytics(tripId: string): Promise<TripAnalytics> {
  return api.get<TripAnalytics>(`/trips/${tripId}/analytics`);
}

export function getMemberAnalytics(tripId: string): Promise<MemberAnalyticsResponse> {
  return api.get<MemberAnalyticsResponse>(`/trips/${tripId}/analytics/members`);
}

export function getRouteAnalytics(tripId: string): Promise<RouteAnalytics> {
  return api.get<RouteAnalytics>(`/trips/${tripId}/analytics/route`);
}

export function getSafetyAnalytics(tripId: string): Promise<SafetyAnalytics> {
  return api.get<SafetyAnalytics>(`/trips/${tripId}/analytics/safety`);
}

export function getTripTimeline(tripId: string): Promise<TripTimeline> {
  return api.get<TripTimeline>(`/trips/${tripId}/timeline`);
}

export function getTripInsights(tripId: string): Promise<TripInsights> {
  return api.get<TripInsights>(`/trips/${tripId}/insights`);
}

export function getTripRisk(tripId: string): Promise<RiskScore> {
  return api.get<RiskScore>(`/trips/${tripId}/risk`);
}

/** GET /trips/{trip_id}/dashboard — the primary aggregated read (Phase
 * 13, item 25). Every dashboard-shaped page composes this ONE call
 * instead of separately fetching trip/route/members/safety/risk/eta/
 * weather/notifications. */
export function getDashboard(tripId: string): Promise<DashboardResponse> {
  return api.get<DashboardResponse>(`/trips/${tripId}/dashboard`);
}
