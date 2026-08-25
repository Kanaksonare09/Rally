'use client';

import { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';
import type { Member } from '@/lib/mock/types';

interface ActivityEntry {
  id: string;
  text: string;
  time: string;
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
      setEntries((prev) => [{ id: `${Date.now()}`, text, time: 'Just now' }, ...prev].slice(0, 8));
    }, 12000);
    return () => clearInterval(interval);
  }, [members]);

  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground mb-4">
        <Activity className="w-4 h-4 text-rally-blue" /> Live Activity
      </h2>
      <div className="space-y-3">
        {entries.map((entry) => (
          <div key={entry.id} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2 text-muted-foreground min-w-0">
              <span className="w-1.5 h-1.5 rounded-full bg-rally-blue shrink-0" />
              <span className="truncate text-foreground">{entry.text}</span>
            </span>
            <span className="text-[11px] text-muted-foreground shrink-0">{entry.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
