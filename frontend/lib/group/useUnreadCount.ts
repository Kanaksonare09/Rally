'use client';

import { useEffect, useState } from 'react';
import { getUnreadCount } from '@/lib/api/notifications';

const POLL_MS = 30_000;

/**
 * Notifications are per-user, not per-trip, so this polls independently
 * of any live group/trip state (Phase 13, item 27) — it's the one
 * deliberate exception to "avoid polling" (item 46): a single lightweight
 * count endpoint every 30s, not a per-second or per-dashboard-card poll,
 * and it's the only way to know about unread notifications on pages with
 * no active group (history, settings) where there's no dashboard fetch
 * to piggyback on.
 */
export function useUnreadCount(): number {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      getUnreadCount()
        .then((r) => {
          if (!cancelled) setCount(r.unread_count);
        })
        .catch(() => {
          // Non-critical — the badge just keeps its last known value
          // rather than surfacing an error for a background poll.
        });
    };
    load();
    const interval = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return count;
}
