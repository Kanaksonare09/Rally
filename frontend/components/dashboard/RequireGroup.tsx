'use client';

import Link from 'next/link';
import { Compass, Loader2 } from 'lucide-react';
import { useGroup } from '@/lib/mock/useGroup';
import type { Group } from '@/lib/mock/types';

export default function RequireGroup({ children }: { children: (group: Group) => React.ReactNode }) {
  const { group, loading } = useGroup();

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
        <p className="text-sm">Loading your group…</p>
      </div>
    );
  }

  if (!group) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-5 px-6 text-center">
        <div className="w-14 h-14 rounded-2xl bg-rally-blue/10 border border-rally-blue/30 flex items-center justify-center text-rally-blue">
          <Compass className="w-7 h-7" />
        </div>
        <div className="space-y-1.5">
          <h1 className="text-xl font-semibold text-foreground">No active Rally yet</h1>
          <p className="text-sm text-muted-foreground max-w-sm">
            Create a new group or join one with a code to see your live dashboard.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/create-group"
            className="px-5 py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
          >
            Create a Rally
          </Link>
          <Link
            href="/join-group"
            className="px-5 py-2.5 rounded-lg border border-border text-foreground text-sm font-semibold hover:bg-white/5 transition-colors"
          >
            Join a Rally
          </Link>
        </div>
      </div>
    );
  }

  return <>{children(group)}</>;
}
