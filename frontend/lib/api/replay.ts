import { api } from './client';
import type { TripReplay } from './types';

/** GET /trips/{trip_id}/replay — backend-sampled (never raw GPS history,
 * see backend/app/analytics/replay.py). `intervalSeconds` is clamped
 * server-side too; the frontend just passes through whatever the replay
 * player's speed control asks for. */
export function getTripReplay(tripId: string, intervalSeconds?: number): Promise<TripReplay> {
  return api.get<TripReplay>(`/trips/${tripId}/replay`, intervalSeconds ? { interval_seconds: intervalSeconds } : undefined);
}
