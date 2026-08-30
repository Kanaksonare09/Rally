import { api } from './client';
import type { ApiRoute, RouteCreate, RouteProgressResponse } from './types';

export function createRoute(tripId: string, input: RouteCreate): Promise<ApiRoute> {
  return api.post<ApiRoute>(`/trips/${tripId}/route`, input);
}

export function getRoute(tripId: string): Promise<ApiRoute> {
  return api.get<ApiRoute>(`/trips/${tripId}/route`);
}

export function getRouteProgress(tripId: string): Promise<RouteProgressResponse> {
  return api.get<RouteProgressResponse>(`/trips/${tripId}/route/progress`);
}
