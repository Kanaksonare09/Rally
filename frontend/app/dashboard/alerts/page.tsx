'use client';

import { useState } from 'react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import AlertFilterBar, { type AlertFilter } from '@/components/dashboard/AlertFilterBar';
import AlertRow from '@/components/dashboard/AlertRow';
import AlertDetailPanel from '@/components/dashboard/AlertDetailPanel';
import { resolveAlert } from '@/lib/api/alerts';
import { friendlyErrorMessage } from '@/lib/api/errors';
import type { AlertItem } from '@/lib/mock/types';
import { BellOff } from 'lucide-react';

export default function AlertsPage() {
  const [filter, setFilter] = useState<AlertFilter>('all');
  const [selected, setSelected] = useState<AlertItem | null>(null);
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);

  return (
    <RequireGroup>
      {(group) => {
        const alerts = group.alerts;
        const total = alerts.length;
        const active = alerts.filter((a) => a.status === 'active').length;
        const resolved = alerts.filter((a) => a.status === 'resolved').length;
        const critical = alerts.filter((a) => a.severity === 'critical').length;

        const filtered = alerts.filter((a) => {
          if (filter === 'all') return true;
          if (filter === 'active') return a.status === 'active';
          if (filter === 'resolved') return a.status === 'resolved';
          if (filter === 'critical' || filter === 'warning') return a.severity === filter;
          return a.type === filter;
        });

        // Phase 13, item 18: never mark an alert resolved locally — send
        // the request, wait for the backend to confirm, then let the
        // real (WebSocket-refreshed) group.alerts state drive the UI.
        // On success we simply close the panel rather than guessing at
        // the resolved shape ourselves; the list behind it re-renders
        // from the real data as soon as RallyGroupService refreshes.
        const handleResolve = async (id: string) => {
          setResolving(true);
          setResolveError(null);
          try {
            await resolveAlert(id);
            setResolving(false);
            setSelected(null);
          } catch (err) {
            setResolving(false);
            setResolveError(friendlyErrorMessage(err));
          }
        };

        const closePanel = () => {
          setSelected(null);
          setResolveError(null);
        };

        return (
          <div className="min-h-screen flex flex-col">
            <Topbar group={group} />

            <div className="flex-1 p-4 md:p-6 space-y-6">
              <div>
                <h1 className="text-xl font-semibold text-foreground">Alerts</h1>
                <p className="text-sm text-muted-foreground mt-1">Monitor everything that needs attention.</p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Total Alerts', value: total, color: 'text-foreground' },
                  { label: 'Active', value: active, color: 'text-amber-400' },
                  { label: 'Resolved', value: resolved, color: 'text-emerald-400' },
                  { label: 'Critical', value: critical, color: 'text-red-400' },
                ].map((s) => (
                  <div key={s.label} className="rounded-2xl border border-border bg-card p-4">
                    <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
                    <p className="text-[11px] text-muted-foreground mt-1">{s.label}</p>
                  </div>
                ))}
              </div>

              <AlertFilterBar active={filter} onChange={setFilter} />

              {filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center gap-2 rounded-2xl border border-border bg-card">
                  <BellOff className="w-6 h-6 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">No alerts match this filter.</p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {filtered.map((alert) => (
                    <AlertRow
                      key={alert.id}
                      alert={alert}
                      onClick={() => {
                        setResolveError(null);
                        setSelected(alert);
                      }}
                    />
                  ))}
                </div>
              )}
            </div>

            {selected && (
              <AlertDetailPanel
                alert={selected}
                onClose={closePanel}
                onResolve={handleResolve}
                resolving={resolving}
                error={resolveError}
              />
            )}
          </div>
        );
      }}
    </RequireGroup>
  );
}
