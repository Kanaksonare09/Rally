'use client';

import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { env } from '@/lib/env';

/**
 * One browser Supabase client for the whole app. Supabase Auth is the
 * ONLY thing this frontend uses Supabase's own client for — every other
 * read/write goes through FastAPI (see lib/api/client.ts). This client
 * never touches the database directly; it exists purely to run the
 * login/signup/session/refresh flows and hand the resulting JWT to the
 * API client.
 *
 * A module-level singleton (not created per-component) so every part of
 * the app shares one session/auth-state-change subscription rather than
 * each mounting its own.
 */
let client: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (client) return client;
  client = createClient(env.supabaseUrl, env.supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });
  return client;
}
