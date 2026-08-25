import type { RouteWaypoint } from './types';

// Solang Valley, near Manali, HP — matches the spec's example destination.
export const DESTINATION = { lat: 32.3172, lng: 77.1561, name: 'Solang Valley' };
export const START_CENTER = { lat: 32.3072, lng: 77.1481 }; // ~1.3km out, final approach to the destination

export function jitter(base: number, spreadKm: number): number {
  // ~1 degree lat ≈ 111km
  return base + (Math.random() - 0.5) * (spreadKm / 111);
}

export function buildRoute(): RouteWaypoint[] {
  const steps = 6;
  const route: RouteWaypoint[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    route.push({
      lat: START_CENTER.lat + (DESTINATION.lat - START_CENTER.lat) * t,
      lng: START_CENTER.lng + (DESTINATION.lng - START_CENTER.lng) * t,
    });
  }
  return route;
}
