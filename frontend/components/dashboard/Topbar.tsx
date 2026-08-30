'use client';

import { Wifi, WifiOff } from 'lucide-react';
import type { Group } from '@/lib/mock/types';
import { useConnectionStatus } from '@/lib/group/useConnectionStatus';
import { useUnreadCount } from '@/lib/group/useUnreadCount';
import NotificationBell from './NotificationBell';

const LIVE_BADGE: Record<string, { label: string; dotClass: string; wrapClass: string; pulse: boolean }> = {
  CONNECTED: { label: 'LIVE', dotClass: 'bg-emerald-400', wrapClass: 'bg-emerald-400/10 border-emerald-400/30 text-emerald-400', pulse: true },
  CONNECTING: { label: 'CONNECTING', dotClass: 'bg-amber-400', wrapClass: 'bg-amber-400/10 border-amber-400/30 text-amber-400', pulse: true },
  RECONNECTING: { label: 'RECONNECTING', dotClass: 'bg-amber-400', wrapClass: 'bg-amber-400/10 border-amber-400/30 text-amber-400', pulse: true },
  ERROR: { label: 'CONNECTION ERROR', dotClass: 'bg-red-400', wrapClass: 'bg-red-400/10 border-red-400/30 text-red-400', pulse: false },
  DISCONNECTED: { label: 'OFFLINE', dotClass: 'bg-muted-foreground', wrapClass: 'bg-white/5 border-border text-muted-foreground', pulse: false },
};

export default function Topbar({ group }: { group: Group | null }) {
  const onlineCount = group?.members.filter((m) => m.online).length ?? 0;
  const total = group?.members.length ?? 0;
  const me = group?.members.find((m) => m.isCurrentUser);

  // Reflects the ACTUAL live-tracking WebSocket state (Phase 13, items
  // 12-14) — not a static "Connected" label. Only meaningful once a
  // group's trip is ACTIVE; otherwise it's just DISCONNECTED because
  // there's nothing to connect to yet, not a failure.
  const wsStatus = useConnectionStatus();
  const badge = LIVE_BADGE[wsStatus] ?? LIVE_BADGE.DISCONNECTED;
  const connected = wsStatus === 'CONNECTED';
  const unreadCount = useUnreadCount();

  return (
    <header className="sticky top-0 z-30 h-16 px-4 md:px-6 flex items-center justify-between bg-card/90 backdrop-blur-md border-b border-border">
      <div className="flex items-center gap-3 md:gap-6 min-w-0">
        <div className="min-w-0">
          <p className="text-[11px] text-muted-foreground leading-none mb-1">Group</p>
          <p className="text-sm font-semibold text-foreground truncate max-w-[160px] md:max-w-none">
            {group?.name ?? 'No active group'}
          </p>
        </div>

        {group && (
          <span className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-bold tracking-wide ${badge.wrapClass}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${badge.dotClass} ${badge.pulse ? 'animate-pulse' : ''}`} />
            {badge.label}
          </span>
        )}

        {group && (
          <span className="hidden sm:inline text-xs font-medium text-muted-foreground">
            {onlineCount}/{total} online
          </span>
        )}
      </div>

      <div className="flex items-center gap-3 md:gap-4 shrink-0">
        {group && (
          <span
            className={`hidden sm:inline-flex items-center gap-1.5 text-xs font-medium ${
              connected ? 'text-muted-foreground' : 'text-red-400'
            }`}
          >
            {connected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            {connected ? 'Connected' : wsStatus === 'CONNECTING' ? 'Connecting…' : wsStatus === 'RECONNECTING' ? 'Reconnecting…' : 'Disconnected'}
          </span>
        )}
        <NotificationBell unreadCount={unreadCount} />
        <div className="w-8 h-8 rounded-full bg-rally-blue/20 border border-rally-blue/40 text-rally-blue font-bold flex items-center justify-center text-xs">
          {(me?.name ?? 'Y').charAt(0)}
        </div>
      </div>
    </header>
  );
}
