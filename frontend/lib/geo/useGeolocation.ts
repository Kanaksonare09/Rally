'use client';

import { useEffect, useRef, useState } from 'react';

/**
 * Wraps `navigator.geolocation.watchPosition`, throttled before anything
 * is actually sent anywhere (Phase 13, item 10) — the browser itself can
 * fire position updates far more often than the backend needs, and
 * MAX_LOCATION_UPDATES_PER_SECOND is a real backend rate limit (see
 * backend README's Rate limiting section), not just a courtesy.
 *
 * Never fabricates accuracy/speed/heading (item 9) — those come through
 * as `null` exactly when the browser didn't provide them (GeolocationCoordinates
 * itself types them as `number | null`), and the caller (submitLocation /
 * the WebSocket client) already treats `null` as "omit this field," not
 * "send 0."
 */

export interface GeoPosition {
  latitude: number;
  longitude: number;
  accuracy: number | null;
  speed: number | null;
  heading: number | null;
  timestamp: number;
}

export type GeoErrorType = 'permission_denied' | 'position_unavailable' | 'timeout' | 'unsupported';

export const LOCATION_UPDATE_INTERVAL_MS = 5000;
export const LOCATION_DISTANCE_THRESHOLD_M = 10;

function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6_371_000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 + Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

interface UseGeolocationOptions {
  enabled: boolean;
  onUpdate: (position: GeoPosition) => void;
  /** LOCATION_UPDATE_INTERVAL — minimum time between two sent updates. */
  minIntervalMs?: number;
  /** LOCATION_DISTANCE_THRESHOLD — a fix within this distance of the
   * last SENT one is skipped even if minIntervalMs has elapsed, so a
   * stationary member doesn't spam identical points. */
  minDistanceMeters?: number;
}

export function useGeolocation({
  enabled,
  onUpdate,
  minIntervalMs = LOCATION_UPDATE_INTERVAL_MS,
  minDistanceMeters = LOCATION_DISTANCE_THRESHOLD_M,
}: UseGeolocationOptions) {
  const [position, setPosition] = useState<GeoPosition | null>(null);
  const [error, setError] = useState<GeoErrorType | null>(null);
  const lastSentRef = useRef<{ lat: number; lon: number; time: number } | null>(null);
  const watchIdRef = useRef<number | null>(null);
  // Holds the latest onUpdate without making it an effect dependency —
  // an inline arrow function passed by the caller would otherwise tear
  // down and restart the browser's watch on every render.
  const onUpdateRef = useRef(onUpdate);
  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    if (!enabled) {
      if (watchIdRef.current !== null) navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
      return;
    }

    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setError('unsupported');
      return;
    }

    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setError(null);
        const next: GeoPosition = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy ?? null,
          speed: pos.coords.speed ?? null,
          heading: pos.coords.heading ?? null,
          timestamp: pos.timestamp,
        };
        setPosition(next);

        const now = Date.now();
        const last = lastSentRef.current;
        const elapsedMs = last ? now - last.time : Infinity;
        const movedMeters = last ? haversineMeters(last.lat, last.lon, next.latitude, next.longitude) : Infinity;

        if (elapsedMs >= minIntervalMs && movedMeters >= minDistanceMeters) {
          lastSentRef.current = { lat: next.latitude, lon: next.longitude, time: now };
          onUpdateRef.current(next);
        }
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) setError('permission_denied');
        else if (err.code === err.POSITION_UNAVAILABLE) setError('position_unavailable');
        else if (err.code === err.TIMEOUT) setError('timeout');
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );

    return () => {
      if (watchIdRef.current !== null) navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    };
  }, [enabled, minIntervalMs, minDistanceMeters]);

  return { position, error };
}

export const GEO_ERROR_MESSAGES: Record<GeoErrorType, string> = {
  permission_denied: 'Location permission required — enable it in your browser settings to share your position.',
  position_unavailable: "Your location couldn't be determined right now.",
  timeout: 'Location is taking longer than expected to determine.',
  unsupported: "This browser doesn't support location sharing.",
};
