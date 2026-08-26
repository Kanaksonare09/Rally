'use client';

import { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';
import type { Member } from '@/lib/mock/types';

interface ActivityEntry {
  id: string;
  text: string;
  time: string;
  isNew?: boolean;
}

const TEMPLATES = (members: Member[]) => [
  `${pick(members)} slowed down`,
  `${pick(members)} location updated`,
  `Group reached checkpoint`,
  `${pick(members)} speed increased`,
  `${pick(members)} rejoined the group`,
];

function pick(members: Member[]) {
  return members[Math.floor(Math.random() * members.length)]?.name ?? 'A member';
}

export default function ActivityFeed({ members }: { members: Member[] }) {
  const [entries, setEntries] = useState<ActivityEntry[]>(() => [
    { id: 'seed-1', text: `${members[0]?.name ?? 'Keshav'} joined the route`, time: 'Just now' },
    { id: 'seed-2', text: `${members[1]?.name ?? 'Aman'} slowed down`, time: '2 min ago' },
    { id: 'seed-3', text: `${members[2]?.name ?? 'Rahul'} location updated`, time: '3 min ago' },
    { id: 'seed-4', text: 'Group reached checkpoint', time: '8 min ago' },
  ]);

  useEffect(() => {
    const interval = setInterval(() => {
      const templates = TEMPLATES(members);
      const text = templates[Math.floor(Math.random() * templates.length)];
      setEntries((prev) => [
        { id: `${Date.now()}`, text, time: 'Just now', isNew: true },
        ...prev.map((e) => ({ ...e, isNew: false })),
      ].slice(0, 6));
    }, 12000);
    return () => clearInterval(interval);
  }, [members]);

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
      </div>

      <div className="pt-2 border-t border-white/10 text-[10px] text-white/30 tracking-widest uppercase">
        Realtime Event Telemetry Stream
      </div>
    </div>
  );
}
