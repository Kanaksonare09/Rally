/**
 * Null-vs-zero-safe formatters (Phase 13, items 24/32/33/40). The
 * backend deliberately returns `null` for "cannot be calculated" and `0`
 * for "genuinely zero" — see the backend README's Analytics section.
 * Every formatter here preserves that distinction: `null`/`undefined`
 * always renders as the given fallback (default "N/A"), never as "0" or
 * "0 km" or "0%".
 */

export function formatDistance(meters: number | null | undefined, fallback = 'N/A'): string {
  if (meters === null || meters === undefined) return fallback;
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

export function formatDuration(seconds: number | null | undefined, fallback = 'N/A'): string {
  if (seconds === null || seconds === undefined) return fallback;
  const totalMinutes = Math.round(seconds / 60);
  if (totalMinutes < 60) return `${totalMinutes} min`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function formatPercent(value: number | null | undefined, fallback = 'N/A'): string {
  if (value === null || value === undefined) return fallback;
  return `${value.toFixed(0)}%`;
}

export function formatSpeedKmh(speedMps: number | null | undefined, fallback = 'N/A'): string {
  if (speedMps === null || speedMps === undefined) return fallback;
  return `${Math.round(speedMps * 3.6)} km/h`;
}

/** ETA specifically: `eta_available=false` must render "ETA unavailable",
 * never "0 min" (Phase 13, item 23) — kept as its own function so no
 * caller can accidentally reach for the generic formatDuration and lose
 * that distinction. */
export function formatEta(etaAvailable: boolean, etaSeconds: number | null | undefined): string {
  if (!etaAvailable || etaSeconds === null || etaSeconds === undefined) return 'ETA unavailable';
  if (etaSeconds <= 0) return 'Arriving now';
  return formatDuration(etaSeconds);
}

export function formatCount(value: number | null | undefined, fallback = 'N/A'): string {
  if (value === null || value === undefined) return fallback;
  return String(value);
}

/** Relative "last seen" phrasing from an ISO timestamp — used instead of
 * ever showing a stale position as if it were current (Phase 13, item 16). */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffSec = Math.max(0, Math.round(diffMs / 1000));
  if (diffSec < 10) return 'Just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHours = Math.round(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.round(diffHours / 24)}d ago`;
}
