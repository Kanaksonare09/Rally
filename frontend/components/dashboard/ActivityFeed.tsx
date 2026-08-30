'use client';

import { useEffect, useRef, useState } from 'react';
import { Activity } from 'lucide-react';
import type { AlertItem, Member } from '@/lib/mock/types';

interface ActivityEntry {
  id: string;
  text: string;
  time: string;
  isNew?: boolean;
}

/**
 * Built entirely from real state changes — member presence transitions
 * (from the live WebSocket's presence_update, surfaced via `online`) and
 * real alerts — never a synthetic/randomly-generated event (Phase 13,
 * item 44/51). An empty feed just means nothing real has happened yet.
 */
export default function ActivityFeed({ members, alerts }: { members: Member[]; alerts: AlertItem[] }) {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const prevOnline = useRef<Map<string, boolean>>(new Map());
  const seenAlertIds = useRef<Set<string>>(new Set());
  const initialized = useRef(false);

  useEffect(() => {
    const additions: ActivityEntry[] = [];

    // Presence transitions — skip the very first render so mounting
    // doesn't fabricate a burst of "X came online" for everyone already
    // present when the page loaded.
    if (initialized.current) {
      for (const m of members) {
        const was = prevOnline.current.get(m.id);
        if (was !== undefined && was !== m.online) {
          additions.push({
            id: `presence-${m.id}-${Date.now()}`,
            text: m.online ? `${m.name} reconnected` : `${m.name} lost connection`,
            time: 'Just now',
            isNew: true,
          });
        }
      }
    }
    prevOnline.current = new Map(members.map((m) => [m.id, m.online]));

    // New alerts (any severity/status) — a real safety event just detected.
    for (const a of alerts) {
      if (!seenAlertIds.current.has(a.id)) {
        seenAlertIds.current.add(a.id);
        if (initialized.current) {
          additions.push({ id: `alert-${a.id}`, text: a.message, time: 'Just now', isNew: true });
        }
      }
    }

    initialized.current = true;
    if (additions.length > 0) {
      setEntries((prev) => [...additions, ...prev.map((e) => ({ ...e, isNew: false }))].slice(0, 8));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [members, alerts]);

  return (
    <div className="rounded-xl border border-white/10 bg-[#0A0A0C] p-5 space-y-4 flex flex-col justify-between h-full font-mono text-xs">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold uppercase tracking-[0.15em] text-white">
              LIVE ACTIVITY
            </h2>
          </div>
          <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-2 py-0.5 rounded-full flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            NOW
          </span>
        </div>

        {/* Activity Stream List */}
        {entries.length === 0 ? (
          <p className="text-xs text-white/40 py-4 text-center">No activity yet — this fills in as things happen.</p>
        ) : (
          <div className="space-y-2">
            {entries.map((entry) => (
              <div
                key={entry.id}
                className={`flex items-center justify-between gap-3 p-2.5 rounded-lg border transition-all duration-300 ${
                  entry.isNew
                    ? 'bg-cyan-400/10 border-cyan-400/30 text-white'
                    : 'bg-[#0B0C10] border-white/5 text-white/80'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      entry.isNew ? 'bg-cyan-400 animate-ping' : 'bg-cyan-400/70'
                    }`}
                  />
                  <span className="truncate text-xs font-medium text-white">
                    {entry.text}
                  </span>
                </div>
                <span className="text-[11px] text-white/40 shrink-0 font-mono">
                  {entry.time}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="pt-2 border-t border-white/10 text-[10px] text-white/30 tracking-widest uppercase">
        Realtime Event Telemetry Stream
      </div>
    </div>
  );
}
