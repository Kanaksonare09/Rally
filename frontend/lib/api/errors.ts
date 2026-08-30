/**
 * The backend's one error envelope (see backend/app/core/errors.py):
 *
 *   { "success": false, "error": { "code": "...", "message": "...",
 *     "request_id": "...", "retry_after_seconds"?: number } }
 *
 * ApiError wraps that shape so every caller can branch on `.code` (a
 * stable machine-readable string) rather than parsing `.message` (a
 * human sentence that can change wording without notice).
 */

export interface BackendErrorBody {
  success: false;
  error: {
    code: string;
    message: string;
    request_id?: string;
    retry_after_seconds?: number;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(status: number, code: string, message: string, requestId: string | null = null, retryAfterSeconds: number | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/** A request that never reached the server at all (offline, DNS failure,
 * CORS, the backend process not running) — distinct from ApiError, which
 * means the server responded, just with a failure. */
export class NetworkError extends Error {
  constructor(message = 'Could not reach the server. Check your connection.') {
    super(message);
    this.name = 'NetworkError';
  }
}

/**
 * Centralized backend-error-code -> user-facing-message mapping (Phase
 * 13, item 45). Falls back to the backend's own `message` for a code this
 * table doesn't know about, rather than a generic "something went wrong"
 * — the backend's messages are already written to be shown to a user
 * (see backend/app/core/errors.py's own docstring), just less specific
 * than these.
 */
const ERROR_MESSAGES: Record<string, string> = {
  UNAUTHORIZED: 'Please sign in again.',
  FORBIDDEN: "You don't have permission to do that.",
  NOT_FOUND: 'That could not be found.',
  TRIP_NOT_FOUND: 'This trip could not be found.',
  GROUP_NOT_FOUND: 'This group could not be found.',
  ROUTE_NOT_FOUND: 'This trip has no route yet.',
  NOTIFICATION_NOT_FOUND: 'That notification could not be found.',
  VALIDATION_ERROR: 'Please check the information you entered.',
  CONFLICT: 'That action could not be completed right now.',
  ACTIVE_TRIP_EXISTS: 'This group already has an active trip.',
  INVALID_TRIP_STATE: 'This trip is not in the right state for that action.',
  INVALID_ROUTE_GEOMETRY: 'This route could not be created — check the origin, destination, and path.',
  ROUTE_NOT_REPLACEABLE: 'This route can no longer be changed.',
  INVALID_SOS_STATE: 'This SOS can no longer be updated.',
  INVALID_ALERT_STATE: 'This alert can no longer be updated.',
  ROUTE_NOT_ACTIVE: 'Route progress is only available once the trip has started.',
  RATE_LIMITED: "You're sending requests too quickly. Please wait a moment.",
  PAYLOAD_TOO_LARGE: 'That request was too large.',
  INTERNAL_ERROR: 'Something went wrong on our end. Please try again.',
  SERVICE_UNAVAILABLE: 'Service temporarily unavailable. Please try again shortly.',
};

export function friendlyErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'RATE_LIMITED' && error.retryAfterSeconds) {
      return `You're sending requests too quickly. Please wait ${error.retryAfterSeconds}s and try again.`;
    }
    return ERROR_MESSAGES[error.code] ?? error.message ?? 'Something went wrong. Please try again.';
  }
  if (error instanceof NetworkError) return error.message;
  if (error instanceof Error) return error.message;
  return 'Something went wrong. Please try again.';
}
