import { api } from './client';
import type { ApiAlert, AlertSeverity, AlertStatus, AlertType } from './types';

export function listTripAlerts(
  tripId: string,
  query: { status?: AlertStatus; severity?: AlertSeverity; alert_type?: AlertType; limit?: number } = {}
): Promise<ApiAlert[]> {
  return api.get<ApiAlert[]>(`/trips/${tripId}/alerts`, query);
}

export function listActiveTripAlerts(tripId: string): Promise<ApiAlert[]> {
  return api.get<ApiAlert[]>(`/trips/${tripId}/alerts/active`);
}

export function getAlert(alertId: string): Promise<ApiAlert> {
  return api.get<ApiAlert>(`/alerts/${alertId}`);
}

/** Every alert mutation flows through the backend and is only reflected
 * in the UI once it responds successfully (Phase 13, item 18) — never
 * mark an alert resolved locally first. */
export function acknowledgeAlert(alertId: string): Promise<ApiAlert> {
  return api.post<ApiAlert>(`/alerts/${alertId}/acknowledge`);
}

export function resolveAlert(alertId: string): Promise<ApiAlert> {
  return api.post<ApiAlert>(`/alerts/${alertId}/resolve`);
}
