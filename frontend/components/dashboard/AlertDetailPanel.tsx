'use client';

import Link from 'next/link';
import { X, Users, MapPin, Clock, ShieldAlert, Lightbulb, Check } from 'lucide-react';
import type { AlertItem } from '@/lib/mock/types';
import { ALERT_TYPE_LABEL } from './AlertRow';

const SEVERITY_TEXT: Record<AlertItem['severity'], string> = {
  critical: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-rally-blue',
};

export default function AlertDetailPanel({
  alert,
  onClose,
  onResolve,
}: {
  alert: AlertItem;
  onClose: () => void;
  onResolve: (id: string) => void;
}) {
  const rows = [
    { icon: Users, label: 'Member', value: alert.memberName ?? '—' },
    { icon: MapPin, label: 'Location', value: alert.location },
    { icon: Clock, label: 'Time', value: alert.time },
    { icon: ShieldAlert, label: 'Severity', value: alert.severity[0].toUpperCase() + alert.severity.slice(1) },
  ];

  return (
    <div className="fixed inset-0 z-[2000] flex justify-end">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full sm:max-w-sm h-full bg-card border-l border-border p-6 overflow-y-auto">
        <button onClick={onClose} aria-label="Close" className="absolute top-5 right-5 text-muted-foreground hover:text-foreground">
          <X className="w-5 h-5" />
        </button>

        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground bg-white/5 px-2.5 py-1 rounded-full inline-block mb-3">
          {ALERT_TYPE_LABEL[alert.type]}
        </span>

        <h2 className="text-lg font-semibold text-foreground mb-1">{alert.message}</h2>
        <p className="text-sm text-muted-foreground mb-6">{alert.detail}</p>

        <div className="space-y-4">
          {rows.map((row) => {
            const Icon = row.icon;
            return (
              <div key={row.label} className="flex items-center justify-between text-sm border-b border-border pb-3">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Icon className="w-4 h-4" /> {row.label}
                </span>
                <span className={`font-medium ${row.label === 'Severity' ? SEVERITY_TEXT[alert.severity] : 'text-foreground'}`}>
                  {row.value}
                </span>
              </div>
            );
          })}
        </div>

        <div className="mt-6 rounded-xl border border-rally-blue/25 bg-rally-blue/5 p-4">
          <p className="flex items-center gap-2 text-xs font-semibold text-rally-blue mb-1.5">
            <Lightbulb className="w-3.5 h-3.5" /> Recommended Action
          </p>
          <p className="text-sm text-foreground">{alert.recommendedAction}</p>
        </div>

        <div className="mt-6 space-y-2.5">
          <Link
            href="/dashboard"
            className="block text-center w-full py-2.5 rounded-lg border border-border text-foreground text-sm font-semibold hover:bg-white/5 transition-colors"
          >
            View on Map
          </Link>
          {alert.status === 'active' ? (
            <button
              onClick={() => onResolve(alert.id)}
              className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
            >
              <Check className="w-4 h-4" /> Resolve Alert
            </button>
          ) : (
            <div className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-emerald-400/10 border border-emerald-400/30 text-emerald-400 text-sm font-semibold">
              <Check className="w-4 h-4" /> Resolved
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
