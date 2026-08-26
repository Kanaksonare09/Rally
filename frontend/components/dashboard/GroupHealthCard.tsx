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
    {
      ok: critical.length === 0,
      label:
        critical.length === 0
          ? 'Group together'
          : `${critical.length} member${critical.length > 1 ? 's' : ''} separated`,
    },
    {
      ok: warning.length === 0,
      label:
        warning.length === 0
          ? 'Everyone on pace'
          : `${warning.length} member${warning.length > 1 ? 's' : ''} slowing down`,
    },
  ];

  const riskColor =
    group.risk.level === 'LOW RISK'
      ? '#34D399'
      : group.risk.level === 'MODERATE RISK'
      ? '#FBBF24'
      : '#F87171';

  return (
    <div className="rounded-xl border border-white/15 bg-[#0A0A0C]/90 backdrop-blur-md p-4 shadow-2xl w-full max-w-xs font-mono text-white">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/50">
            GROUP HEALTH
          </p>
          <p className="text-xs font-medium text-white/70 mt-0.5">
            {onlineCount} / {group.members.length} members online
          </p>
          <p className="text-[11px] font-bold tracking-wider mt-1" style={{ color: riskColor }}>
            {group.risk.level}
          </p>
        </div>
        <div className="shrink-0">
          <RiskRing risk={group.risk} size={64} />
        </div>
      </div>

      <div className="space-y-1.5 pt-2 border-t border-white/10 text-xs">
        {insights.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-white/80">
            {item.ok ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            )}
            <span className={item.ok ? 'text-white/60' : 'text-amber-300 font-semibold'}>
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
