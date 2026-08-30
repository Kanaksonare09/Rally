import { api } from './client';
import type { ApiSOSEvent, SOSCreate, SOSStatus } from './types';

/** POST /trips/{trip_id}/sos — the backend is idempotent for this call
 * (an already-ACTIVE SOS for the same user/trip is returned as-is, never
 * duplicated — see backend/app/sos/service.py), so the frontend never
 * needs its own duplicate-submission guard beyond normal button
 * disabling while a request is in flight. */
export function triggerSOS(tripId: string, input: SOSCreate): Promise<ApiSOSEvent> {
  return api.post<ApiSOSEvent>(`/trips/${tripId}/sos`, input);
}

export function listTripSOS(tripId: string, query: { status?: SOSStatus; limit?: number } = {}): Promise<ApiSOSEvent[]> {
  return api.get<ApiSOSEvent[]>(`/trips/${tripId}/sos`, query);
}

export function listActiveTripSOS(tripId: string): Promise<ApiSOSEvent[]> {
  return api.get<ApiSOSEvent[]>(`/trips/${tripId}/sos/active`);
}

export function acknowledgeSOS(sosId: string): Promise<ApiSOSEvent> {
  return api.post<ApiSOSEvent>(`/sos/${sosId}/acknowledge`);
}

export function resolveSOS(sosId: string): Promise<ApiSOSEvent> {
  return api.post<ApiSOSEvent>(`/sos/${sosId}/resolve`);
}

/** Only the user who triggered a given SOS may cancel it — enforced by
 * the backend regardless of what the frontend shows. */
export function cancelSOS(sosId: string): Promise<ApiSOSEvent> {
  return api.post<ApiSOSEvent>(`/sos/${sosId}/cancel`);
}
