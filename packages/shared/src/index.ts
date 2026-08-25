// RALLY Constants & Design Tokens

export const RALLY_DESIGN_TOKENS = {
  colors: {
    background: '#05070A',
    card: '#0D1219',
    cardBorder: 'rgba(255, 255, 255, 0.08)',
    textPrimary: '#F5F7FA',
    textMuted: '#8C96A5',
    brandBlue: '#19BFFF',
    brandBlueGlow: 'rgba(25, 191, 255, 0.25)',
    warning: '#F59E0B',
    danger: '#EF4444',
    success: '#22C55E',
  },
} as const;

export const DEFAULT_GROUP_THRESHOLDS = {
  SAFE_DISTANCE_M: 150.0,
  DRIFTING_DISTANCE_M: 250.0,
  CRITICAL_SEPARATION_M: 350.0,
  ROUTE_DEVIATION_M: 100.0,
  UNEXPECTED_STOP_DURATION_SEC: 180, // 3 minutes
  LOCATION_UPDATE_INTERVAL_MS: 5000, // 5 sec
} as const;

// Distance calculation helpers (Haversine formula)
export function calculateHaversineDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${Math.round(meters)} m`;
  }
  return `${(meters / 1000).toFixed(1)} km`;
}

export function formatSpeed(speedMps?: number): string {
  if (speedMps === undefined || speedMps === null) return '0 km/h';
  const kmh = speedMps * 3.6;
  return `${Math.round(kmh)} km/h`;
}
