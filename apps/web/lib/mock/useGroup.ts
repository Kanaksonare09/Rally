'use client';

import { useEffect, useState } from 'react';
import { groupService } from './groupService';
import type { Group } from './types';

export function useGroup() {
  // Always start null/loading — even on the client — so the first render
  // matches the server-rendered HTML. The module-level groupService singleton
  // reads localStorage synchronously at import time, so calling
  // getCurrentGroup() here in the initializer would return real data before
  // hydration even runs, causing a mismatch against the server's null render.
  const [group, setGroup] = useState<Group | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setGroup(groupService.getCurrentGroup());
    setLoading(false);
    return groupService.subscribe(setGroup);
  }, []);

  return { group, loading };
}
