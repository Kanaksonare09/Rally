'use client';

import { useEffect, useState } from 'react';
import { groupService } from './groupService';
import type { Group } from '@/lib/mock/types';

/** The real-backend equivalent of lib/mock/useGroup.ts — same hook
 * shape (`{ group, loading }`), backed by RallyGroupService instead of
 * localStorage. subscribe() triggers the service's lazy init (fetching
 * the caller's groups/trips) on first subscriber. */
export function useGroup() {
  const [group, setGroup] = useState<Group | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = groupService.subscribe((next) => {
      setGroup(next);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  return { group, loading };
}
