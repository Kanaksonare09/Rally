'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { getSupabaseClient } from '@/lib/supabase/client';

interface AuthContextValue {
  session: Session | null;
  user: User | null;
  /** True until the very first session check (localStorage restore)
   * completes — consumers use this to avoid flashing a "logged out" UI
   * before Supabase has had a chance to restore an existing session. */
  loading: boolean;
  accessToken: string | null;
  signInWithPassword: (email: string, password: string) => Promise<{ error: string | null }>;
  signUpWithPassword: (email: string, password: string, fullName?: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = getSupabaseClient();
    let active = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setLoading(false);
    });

    // Fires on sign-in, sign-out, AND every automatic token refresh — the
    // one place session/token state changes, so every consumer (the API
    // client, the WebSocket client) always sees the current token without
    // polling.
    const { data: subscription } = supabase.auth.onAuthStateChange((_event, newSession) => {
      if (!active) return;
      setSession(newSession);
      setLoading(false);
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  const signInWithPassword = useCallback(async (email: string, password: string) => {
    const { data, error } = await getSupabaseClient().auth.signInWithPassword({ email, password });
    // Update context state directly from the response rather than waiting
    // on onAuthStateChange above — supabase-js dispatches that listener via
    // a deferred setTimeout(0), so a caller that awaits this and then
    // immediately navigates (see app/(auth)/login/page.tsx) can otherwise
    // land on a protected page before the listener ever fires, and
    // RequireAuth bounces them straight back to /login having seen a
    // stale null session.
    if (!error) setSession(data.session);
    return { error: error?.message ?? null };
  }, []);

  const signUpWithPassword = useCallback(async (email: string, password: string, fullName?: string) => {
    const { data, error } = await getSupabaseClient().auth.signUp({
      email,
      password,
      options: fullName ? { data: { full_name: fullName } } : undefined,
    });
    // Same race as signInWithPassword above. `data.session` is null when
    // Supabase's email-confirmation flow is on (expected, not a bug) —
    // setting it to null here is a no-op against the already-null state.
    if (!error) setSession(data.session);
    return { error: error?.message ?? null };
  }, []);

  const signOut = useCallback(async () => {
    await getSupabaseClient().auth.signOut();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      loading,
      accessToken: session?.access_token ?? null,
      signInWithPassword,
      signUpWithPassword,
      signOut,
    }),
    [session, loading, signInWithPassword, signUpWithPassword, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>.');
  return ctx;
}

/** Returns a stable getter the WebSocket client / anything outside React
 * render can call for the CURRENT token on demand, without re-rendering
 * every time it changes. */
export async function getCurrentAccessToken(): Promise<string | null> {
  const { data } = await getSupabaseClient().auth.getSession();
  return data.session?.access_token ?? null;
}
