'use client';

import { Loader2 } from 'lucide-react';
import { useGroup } from '@/lib/mock/useGroup';
import type { Group } from '@/lib/mock/types';
import EmptyRallyState from '@/components/dashboard/EmptyRallyState';

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
      <div className="min-h-screen flex flex-col items-center justify-center">
        <EmptyRallyState />
      </div>
    );
  }

  return <>{children(group)}</>;
}
