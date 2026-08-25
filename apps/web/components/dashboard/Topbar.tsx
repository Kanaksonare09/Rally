'use client';

import { Wifi, WifiOff } from 'lucide-react';
import type { Group } from '@/lib/mock/types';

export default function Topbar({ group, online = true }: { group: Group | null; online?: boolean }) {
  const onlineCount = group?.members.filter((m) => m.online).length ?? 0;
  const total = group?.members.length ?? 0;
  const me = group?.members.find((m) => m.isCurrentUser);

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
          <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-400/10 border border-emerald-400/30 text-[11px] font-bold text-emerald-400 tracking-wide">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            LIVE
          </span>
        )}

        {group && (
          <span className="hidden sm:inline text-xs font-medium text-muted-foreground">
            {onlineCount}/{total} online
          </span>
        )}
      </div>

      <div className="flex items-center gap-3 md:gap-4 shrink-0">
        <span
          className={`hidden sm:inline-flex items-center gap-1.5 text-xs font-medium ${
            online ? 'text-muted-foreground' : 'text-red-400'
          }`}
        >
          {online ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
          {online ? 'Connected' : 'Reconnecting…'}
        </span>
        <div className="w-8 h-8 rounded-full bg-rally-blue/20 border border-rally-blue/40 text-rally-blue font-bold flex items-center justify-center text-xs">
          {(me?.name ?? 'Y').charAt(0)}
        </div>
      </div>
    </header>
  );
}
