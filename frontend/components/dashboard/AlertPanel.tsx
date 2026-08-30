'use client';

import { AlertTriangle, Radio, ShieldAlert, BellOff } from 'lucide-react';
import type { AlertItem } from '@/lib/mock/types';

const SEVERITY_STYLE: Record<AlertItem['severity'], { icon: React.ElementType; color: string; bg: string; border: string }> = {
  critical: { icon: ShieldAlert, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  high: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
  warning: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/20' },
  info: { icon: Radio, color: 'text-rally-blue', bg: 'bg-rally-blue/10', border: 'border-rally-blue/20' },
};

export default function AlertPanel({ alerts }: { alerts: AlertItem[] }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-foreground">Alerts</h2>
        {alerts.length > 0 && (
          <span className="text-[11px] font-semibold text-muted-foreground">{alerts.length} active</span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center gap-2">
          <BellOff className="w-6 h-6 text-muted-foreground" />
          <p className="text-xs text-muted-foreground">No alerts. Everyone&apos;s on track.</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {alerts.map((alert) => {
            const style = SEVERITY_STYLE[alert.severity];
            const Icon = style.icon;
            return (
              <div key={alert.id} className={`flex items-start gap-3 p-3 rounded-xl border ${style.bg} ${style.border}`}>
                <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${style.color}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-foreground">{alert.message}</p>
                    <span className="text-[10px] text-muted-foreground whitespace-nowrap">{alert.time}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{alert.detail}</p>
                  {alert.memberName && (
                    <span className="inline-block mt-1.5 text-[10px] font-medium text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">
                      {alert.memberName}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
