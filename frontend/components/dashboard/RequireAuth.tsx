'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/lib/auth/AuthProvider';

/**
 * The auth-only half of RequireGroup, split out so pages that don't need
 * a live group (trip history, settings) still get the same client-side
 * "redirect to /login if there's no session" protection — every real
 * /dashboard/* page needs SOME auth gate, not just the ones that also
 * happen to need a group (Phase 13, item 4/5).
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) {
      const redirect = typeof window !== 'undefined' ? window.location.pathname : '/dashboard';
      router.replace(`/login?redirect=${encodeURIComponent(redirect)}`);
    }
  }, [authLoading, user, router]);

  if (authLoading || (!user && typeof window !== 'undefined')) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
        <p className="text-sm">Checking your session…</p>
      </div>
    );
  }

  return <>{children}</>;
}
