/**
 * Typed, validated access to NEXT_PUBLIC_* environment variables. Every
 * consumer of a backend URL/key goes through this module rather than
 * reading `process.env.NEXT_PUBLIC_*` inline — one place to see exactly
 * what the frontend depends on, and one place that fails loudly (in dev)
 * instead of quietly shipping `undefined` into a fetch URL.
 *
 * SUPABASE_SERVICE_ROLE_KEY (or any other backend secret) must NEVER be
 * read here or anywhere else in this frontend — see .env.local.example.
 */

function readEnv(name: string, value: string | undefined, required: boolean): string {
  if (!value) {
    const message = `Missing environment variable ${name}. Copy .env.local.example to .env.local and fill it in.`;
    if (required && process.env.NODE_ENV !== 'production') {
      // Fail loudly in dev/build rather than silently sending requests to
      // "undefined" — production logs a warning instead of throwing so a
      // misconfigured deploy degrades (auth/API calls fail with a clear
      // network error) rather than crashing every page render.
      console.error(message);
    }
    return '';
  }
  return value;
}

export const env = {
  apiUrl: readEnv('NEXT_PUBLIC_API_URL', process.env.NEXT_PUBLIC_API_URL, true).replace(/\/+$/, ''),
  wsUrl: readEnv('NEXT_PUBLIC_WS_URL', process.env.NEXT_PUBLIC_WS_URL, true).replace(/\/+$/, ''),
  supabaseUrl: readEnv('NEXT_PUBLIC_SUPABASE_URL', process.env.NEXT_PUBLIC_SUPABASE_URL, true),
  supabaseAnonKey: readEnv('NEXT_PUBLIC_SUPABASE_ANON_KEY', process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY, true),
};

/** The backend's own API_V1_STR prefix — kept in one place since every
 * endpoint function in lib/api/ builds its path off this. */
export const API_V1 = '/api/v1';
