'use client';

import { useCallback } from 'react';
import { rallyGroupServiceLocation } from '@/lib/realtime/RallyGroupService';
import { useGeolocation, type GeoErrorType, type GeoPosition } from './useGeolocation';

/**
 * Wires the browser geolocation watcher to the live trip's WebSocket —
 * the one place a component needs to opt a trip page into "start sharing
 * my location." `enabled` should be `trip.status === 'ACTIVE' && !trip.paused`;
 * the underlying watcher/socket send is a genuine no-op otherwise (see
 * RallyGroupService.sendLocationUpdate).
 */
export function useTripLocationSharing(enabled: boolean): { position: GeoPosition | null; error: GeoErrorType | null } {
  const onUpdate = useCallback((position: GeoPosition) => {
    rallyGroupServiceLocation.sendLocationUpdate({
      latitude: position.latitude,
      longitude: position.longitude,
      accuracy: position.accuracy,
      speed: position.speed,
      heading: position.heading,
    });
  }, []);

  return useGeolocation({ enabled, onUpdate });
}
