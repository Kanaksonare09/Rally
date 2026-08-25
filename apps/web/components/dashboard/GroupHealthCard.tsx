'use client';

import { CheckCircle2, AlertTriangle } from 'lucide-react';
import type { Group } from '@/lib/mock/types';
import RiskRing from './RiskRing';

export default function GroupHealthCard({ group }: { group: Group }) {
  const onlineCount = group.members.filter((m) => m.online).length;
  const critical = group.members.filter((m) => m.status === 'critical');
  const warning = group.members.filter((m) => m.status === 'warning');

  const insights = [
    { ok: true, label: 'Route aligned' },
    { ok: critical.length === 0, label: critical.length === 0 ? 'Group together' : `${critical.length} member${critical.length > 1 ? 's' : ''} separated` },
    { ok: warning.length === 0, label: warning.length === 0 ? 'Everyone on pace' : `${warning.length} member${warning.length > 1 ? 's' : ''} slowing down` },
  ];

  return (
    <div className="rounded-2xl border border-border bg-card/95 backdrop-blur-md p-5 shadow-2xl shadow-black/60 w-full max-w-xs">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-[11px] font-semibold text-muted-foreground tracking-wider">GROUP HEALTH</p>
          <p className="text-xs font-medium text-muted-foreground mt-1">{onlineCount} / {group.members.length} members online</p>
        </div>
        <RiskRing risk={group.risk} size={72} />
      </div>

      <p className="text-xs font-bold tracking-wide mb-3" style={{ color: group.risk.level === 'LOW RISK' ? '#34D399' : group.risk.level === 'MODERATE RISK' ? '#FBBF24' : '#F87171' }}>
        {group.risk.level}
      </p>

      <div className="space-y-2">
        {insights.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-xs text-muted-foreground">
            {item.ok ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            )}
            <span className={item.ok ? '' : 'text-foreground'}>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
