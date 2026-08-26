'use client';

import React from 'react';
import Link from 'next/link';
import { AlertTriangle, ShieldAlert, Radio, ArrowRight, BellOff } from 'lucide-react';
import type { AlertItem } from '@/lib/mock/types';

const SEVERITY_CONFIG: Record<
  AlertItem['severity'],
  { label: string; icon: React.ElementType; color: string; badgeBg: string; border: string }
> = {
  critical: {
    label: 'CRITICAL',
    icon: ShieldAlert,
    color: 'text-red-400',
    badgeBg: 'bg-red-500/10 text-red-400 border-red-500/30',
    border: 'border-red-500/30 bg-red-500/[0.04]',
  },
  warning: {
    label: 'WARNING',
    icon: AlertTriangle,
    color: 'text-amber-400',
    badgeBg: 'bg-amber-400/10 text-amber-400 border-amber-400/30',
    border: 'border-white/10 bg-[#0B0C10]',
  },
  info: {
    label: 'CONNECTIVITY',
    icon: Radio,
    color: 'text-cyan-400',
    badgeBg: 'bg-cyan-400/10 text-cyan-400 border-cyan-400/30',
    border: 'border-white/10 bg-[#0B0C10]',
  },
};

export default function NeedsAttentionPanel({ alerts }: { alerts: AlertItem[] }) {
  const activeAlerts = alerts.filter((a) => a.status === 'active');

  return (
    <div className="rounded-xl border border-white/10 bg-[#0A0A0C] p-5 space-y-4 flex flex-col justify-between h-full">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between font-mono">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <h2 className="text-xs font-bold uppercase tracking-[0.15em] text-white">
              NEEDS ATTENTION
            </h2>
          </div>
          <span className="text-[11px] font-semibold text-white/50 bg-white/5 border border-white/10 px-2 py-0.5 rounded-full">
            {activeAlerts.length} active
          </span>
        </div>

        {/* Alert List */}
        {activeAlerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center gap-2">
            <BellOff className="w-5 h-5 text-white/30" />
            <p className="text-xs text-white/50">No active alerts. All group members on track.</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {activeAlerts.map((alert) => {
              const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.warning;
              const Icon = config.icon;
              return (
                <Link
                  key={alert.id}
                  href="/dashboard/alerts"
                  className={`block p-3 rounded-lg border transition-all duration-200 hover:border-white/20 group ${config.border}`}
                >
                  <div className="flex items-start justify-between gap-2 font-mono text-[11px] mb-1.5">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-bold tracking-wider ${config.badgeBg}`}
                    >
                      <Icon className="w-3 h-3" />
                      {config.label}
                    </span>
                    <span className="text-white/40">{alert.time}</span>
                  </div>

                  <p className="text-xs font-medium text-white group-hover:text-cyan-300 transition-colors">
                    {alert.message}
                  </p>

                  <p className="text-[11px] text-white/50 mt-0.5">
                    {alert.detail}
                  </p>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer Link */}
      <div className="pt-2 border-t border-white/10">
        <Link
          href="/dashboard/alerts"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
        >
          <span>View all alerts</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
