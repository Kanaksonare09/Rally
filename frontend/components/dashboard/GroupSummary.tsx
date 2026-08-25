'use client';

import type { Member } from '@/lib/mock/types';

export default function GroupSummary({ members }: { members: Member[] }) {
  const online = members.filter((m) => m.online).length;
  const offline = members.length - online;
  const safe = members.filter((m) => m.status === 'safe').length;
  const warning = members.filter((m) => m.status === 'warning').length;
  const critical = members.filter((m) => m.status === 'critical').length;

  const items = [
    { label: 'Total', value: members.length, color: 'text-foreground' },
    { label: 'Online', value: online, color: 'text-emerald-400' },
    { label: 'Offline', value: offline, color: 'text-slate-400' },
    { label: 'Safe', value: safe, color: 'text-emerald-400' },
    { label: 'Warning', value: warning, color: 'text-amber-400' },
    { label: 'Critical', value: critical, color: 'text-red-400' },
  ];

  return (
    <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
      {items.map((item) => (
        <div key={item.label} className="rounded-2xl border border-border bg-card p-4 text-center">
          <p className={`text-xl font-bold ${item.color}`}>{item.value}</p>
          <p className="text-[11px] text-muted-foreground mt-1">{item.label}</p>
        </div>
      ))}
    </div>
  );
}
