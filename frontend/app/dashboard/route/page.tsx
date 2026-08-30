'use client';

import { useEffect, useState } from 'react';
import { Navigation, Ruler, Clock, Percent, CloudSun, AlertTriangle } from 'lucide-react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import LiveMap from '@/components/map/LiveMap';
import { rallyGroupServiceLocation } from '@/lib/realtime/RallyGroupService';
import { formatDistance, formatEta, formatPercent } from '@/lib/format';
import type { Group } from '@/lib/mock/types';
import type { DashboardResponse } from '@/lib/api/types';

export default function RoutePage() {
  return <RequireGroup>{(group) => <RouteContent group={group} />}</RequireGroup>;
}

function RouteContent({ group }: { group: Group }) {
  // The dashboard call already happens inside RallyGroupService's refresh
  // cycle (Phase 13, item 25/46 — one dashboard fetch feeds every card,
  // no per-widget requests); this just reads the cached result back out,
  // re-synced every time `group` changes.
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(() => rallyGroupServiceLocation.getLastDashboard());

  useEffect(() => {
    setDashboard(rallyGroupServiceLocation.getLastDashboard());
  }, [group]);

  const route = dashboard?.route;
  const activeAlerts = group.alerts.filter((a) => a.status === 'active');
  const deviationAlert = activeAlerts.find((a) => a.type === 'route_deviation');

  return (
    <div className="min-h-screen flex flex-col">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 space-y-5">
        <h1 className="text-xl font-semibold text-foreground">Route</h1>

        {deviationAlert && (
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-medium">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            {deviationAlert.memberName ?? 'A member'} has drifted off the planned route.
          </div>
        )}

        {!route?.route_available ? (
          <div className="rounded-2xl border border-border bg-card p-4 text-sm text-muted-foreground">
            No route has been set for this trip yet.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Group Progress" value={formatPercent(route.progress_percent)} icon={Percent} />
            <StatCard label="Distance Remaining" value={formatDistance(route.distance_remaining_meters)} icon={Ruler} />
            <StatCard label="Total Distance" value={formatDistance(route.distance_meters)} icon={Navigation} />
            <StatCard
              label="Group ETA"
              value={formatEta(dashboard?.eta.group_eta_available ?? false, dashboard?.eta.group_eta_seconds ?? null)}
              icon={Clock}
            />
          </div>
        )}

        <div className="h-[55vh] min-h-[380px]">
          <LiveMap group={group} showStart alerts={activeAlerts} />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-border bg-card p-4">
            <h2 className="text-sm font-semibold text-foreground mb-3">Member Progress</h2>
            {dashboard && dashboard.members.length > 0 ? (
              <div className="space-y-2.5">
                {dashboard.members.map((m) => {
                  const name = group.members.find((mem) => mem.id === m.user_id)?.name ?? m.name ?? 'Member';
                  return (
                    <div key={m.user_id} className="flex items-center justify-between text-sm">
                      <span className="text-foreground">{name}</span>
                      <span className="text-muted-foreground">{formatPercent(m.progress_percent)}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No progress data yet.</p>
            )}
          </div>

          <div className="rounded-2xl border border-border bg-card p-4">
            <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
              <CloudSun className="w-4 h-4 text-muted-foreground" /> Weather
            </h2>
            {dashboard?.weather.weather_available ? (
              <div className="space-y-1.5 text-sm">
                <p className="text-foreground font-medium">
                  {dashboard.weather.condition ?? 'Unknown'}
                  {dashboard.weather.temperature_celsius != null ? ` · ${Math.round(dashboard.weather.temperature_celsius)}°C` : ''}
                </p>
                {dashboard.weather.warnings.length > 0 && (
                  <ul className="text-amber-400 text-xs space-y-0.5">
                    {dashboard.weather.warnings.map((w, i) => (
                      <li key={i}>{w.reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Weather unavailable</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon }: { label: string; value: string; icon: React.ElementType }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <Icon className="w-4 h-4 text-muted-foreground mb-2" />
      <p className="text-lg font-bold text-foreground leading-none">{value}</p>
      <p className="text-[11px] text-muted-foreground mt-1.5">{label}</p>
    </div>
  );
}
