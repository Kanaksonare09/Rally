import { api } from './client';
import type { LocationCreate, LocationResponse } from './types';

/** POST /trips/{trip_id}/locations — REST GPS ingestion. Live-tracking
 * pages send updates over the WebSocket instead (see lib/ws/client.ts);
 * this REST path exists for the rare case of one-off submission (or if a
 * WS connection isn't available), and for the browser-geolocation hook's
 * very first fix before a socket is open. */
export function submitLocation(tripId: string, input: LocationCreate): Promise<LocationResponse> {
  return api.post<LocationResponse>(`/trips/${tripId}/locations`, input);
}

export function getLocationHistory(
  tripId: string,
  query: { from?: string; to?: string; user_id?: string; limit?: number; cursor?: string } = {}
): Promise<LocationResponse[]> {
  return api.get<LocationResponse[]>(`/trips/${tripId}/locations`, query);
}
