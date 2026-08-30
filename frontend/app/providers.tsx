'use client';

import { AuthProvider } from '@/lib/auth/AuthProvider';

/** Client-side context providers, kept out of the (server) root layout —
 * app/layout.tsx stays a server component; this is the one client
 * boundary that wraps the whole tree. */
export function Providers({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
