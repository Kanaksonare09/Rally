'use client';

import { AlertTriangle, ShieldAlert, Radio, MapPin, Users, Navigation2, Siren } from 'lucide-react';
import type { AlertItem, AlertType } from '@/lib/mock/types';

const SEVERITY_STYLE: Record<AlertItem['severity'], { color: string; bg: string; border: string }> = {
  critical: { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30' },
  high: { color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30' },
  warning: { color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/30' },
  info: { color: 'text-rally-blue', bg: 'bg-rally-blue/10', border: 'border-rally-blue/30' },
};

export const ALERT_TYPE_ICON: Record<AlertType, React.ElementType> = {
  separation: Users,
  route_deviation: Navigation2,
  connectivity: Radio,
  stop: AlertTriangle,
  sos: Siren,
};

export const ALERT_TYPE_LABEL: Record<AlertType, string> = {
  separation: 'Separation',
  route_deviation: 'Route Deviation',
  connectivity: 'Connectivity',
  stop: 'Unexpected Stop',
  sos: 'SOS',
};

export default function AlertRow({ alert, onClick }: { alert: AlertItem; onClick: () => void }) {
  const style = SEVERITY_STYLE[alert.severity];
  const Icon = alert.severity === 'critical' ? ShieldAlert : ALERT_TYPE_ICON[alert.type];

  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-2xl border p-4 transition-colors hover:border-white/20 ${style.bg} ${style.border}`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${style.color}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm font-semibold text-foreground">{alert.message}</p>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">
                {ALERT_TYPE_LABEL[alert.type]}
              </span>
              <span
                className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${
                  alert.status === 'resolved'
                    ? 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10'
                    : 'text-amber-400 border-amber-400/30 bg-amber-400/10'
                }`}
              >
                {alert.status === 'resolved' ? 'Resolved' : 'Active'}
              </span>
            </div>
            <span className="text-[11px] text-muted-foreground whitespace-nowrap">{alert.time}</span>
          </div>

          <p className="text-sm text-muted-foreground mt-1">{alert.detail}</p>

          <div className="flex items-center gap-4 mt-2.5 text-[11px] text-muted-foreground">
            {alert.memberName && (
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" /> {alert.memberName}
              </span>
            )}
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3" /> {alert.location}
            </span>
          </div>
        </div>
      </div>
    </button>
  );
}
