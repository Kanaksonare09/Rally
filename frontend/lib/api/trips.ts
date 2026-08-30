import { api } from './client';
import type { ApiTrip, TripHistoryQuery, TripHistoryResponse } from './types';

export function createTrip(groupId: string, input: { destination_name?: string; latitude?: number; longitude?: number }): Promise<ApiTrip> {
  return api.post<ApiTrip>(`/groups/${groupId}/trips`, input);
}

export function getTrip(tripId: string): Promise<ApiTrip> {
  return api.get<ApiTrip>(`/trips/${tripId}`);
}

/** CREATED -> ACTIVE. Trip state is always decided by the backend — the
 * frontend never flips a trip to ACTIVE/COMPLETED/CANCELLED locally. */
export function startTrip(tripId: string, input?: { latitude?: number; longitude?: number }): Promise<ApiTrip> {
  return api.post<ApiTrip>(`/trips/${tripId}/start`, input);
}

export function endTrip(tripId: string): Promise<ApiTrip> {
  return api.post<ApiTrip>(`/trips/${tripId}/end`);
}

export function cancelTrip(tripId: string): Promise<ApiTrip> {
  return api.post<ApiTrip>(`/trips/${tripId}/cancel`);
}

export function listMyTripHistory(query: TripHistoryQuery = {}): Promise<TripHistoryResponse> {
  return api.get<TripHistoryResponse>('/users/me/trips', query);
}

export function listGroupTripHistory(groupId: string, query: TripHistoryQuery = {}): Promise<TripHistoryResponse> {
  return api.get<TripHistoryResponse>(`/groups/${groupId}/trips`, query);
}
