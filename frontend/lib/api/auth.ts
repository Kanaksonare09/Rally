import { api } from './client';
import type { MeResponse } from './types';

/** GET /auth/me — the authenticated user's profile, per the verified JWT.
 * Actual login/signup/logout go through Supabase directly (lib/auth/AuthProvider.tsx)
 * — FastAPI never issues its own tokens, it only verifies Supabase's. */
export function getMe(): Promise<MeResponse> {
  return api.get<MeResponse>('/auth/me');
}
