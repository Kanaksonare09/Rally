'use client';

import { useEffect, useState } from 'react';
import { rallyGroupServiceLocation } from '@/lib/realtime/RallyGroupService';
import type { ConnectionStatus } from '@/lib/ws/types';

/** The real live-tracking WebSocket's connection state (Phase 13, items
 * 12-14) — CONNECTED/CONNECTING/DISCONNECTED/RECONNECTING/ERROR, never a
 * hardcoded "Connected". DISCONNECTED with no group/live trip just means
 * there's currently nothing to connect to, not a failure. */
export function useConnectionStatus(): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>(() => rallyGroupServiceLocation.getConnectionStatus());

  useEffect(() => rallyGroupServiceLocation.subscribeConnectionStatus(setStatus), []);

  return status;
}
