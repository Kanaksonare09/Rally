import { ApiError } from './errors';
import { api } from './client';
import type { DemoResetResponse, DemoScenarioResponse, DemoStatusResponse } from './types';

/**
 * The backend's demo control API (backend/app/api/demo.py) only exists at
 * all when the backend was started with DEMO_MODE=true — every route
 * below is a genuine 404 otherwise (no route registered), never a 403.
 * `isDemoModeAvailable()` is how the frontend finds that out: try
 * /demo/status once and treat a 404 as "not available" rather than an
 * error to show the user.
 */

export async function isDemoModeAvailable(): Promise<boolean> {
  try {
    await api.get<DemoStatusResponse>('/demo/status');
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return false;
    throw err;
  }
}

export function getDemoStatus(): Promise<DemoStatusResponse> {
  return api.get<DemoStatusResponse>('/demo/status');
}

export function resetDemo(): Promise<DemoResetResponse> {
  return api.post<DemoResetResponse>('/demo/reset');
}

export function startDemoScenario(scenario: string): Promise<DemoScenarioResponse> {
  return api.post<DemoScenarioResponse>(`/demo/scenarios/${scenario}/start`);
}

export function stopDemoScenario(scenario: string): Promise<DemoStatusResponse> {
  return api.post<DemoStatusResponse>(`/demo/scenarios/${scenario}/stop`);
}
