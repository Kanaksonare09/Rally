'use client';

import Link from 'next/link';
import { ArrowRight, Route, Clock, Users, BellRing, Navigation2 } from 'lucide-react';
import type { TripSummary } from '@/lib/mock/types';
import { formatDistance, formatDuration, formatCount } from '@/lib/format';

const LEVEL_COLOR: Record<NonNullable<TripSummary['riskLevel']>, string> = {
  'LOW RISK': 'text-emerald-400',
  'MODERATE RISK': 'text-amber-400',
  'HIGH RISK': 'text-red-400',
};

/**
 * The real `GET /users/me/trips` list endpoint only returns lightweight
 * summary fields (see backend TripHistoryItem) — no safety score, alert
 * count, or deviation count, which only the per-trip analytics/insights
 * endpoints compute. Those fields are optional here and rendered as
 * "N/A" rather than fabricated 0s (Phase 13, items 24/32/46); the full
 * numbers appear once the trip-summary page loads that one trip's detail.
 */
export interface HistoryTripSummary {
  id: string;
  groupName: string;
  date: string;
  distanceKm: number | null;
  durationMin: number | null;
  membersCount: number;
  alertsCount: number | null;
  routeDeviations: number | null;
  safetyScore: number | null;
  riskLevel: TripSummary['riskLevel'] | null;
}

export default function TripHistoryCard({ trip }: { trip: HistoryTripSummary }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 flex flex-col sm:flex-row sm:items-center gap-5">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <h3 className="text-base font-semibold text-foreground">{trip.groupName}</h3>
          <span className="text-xs text-muted-foreground">{trip.date}</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 mt-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Route className="w-3.5 h-3.5" /> {formatDistance(trip.distanceKm != null ? trip.distanceKm * 1000 : null)}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" /> {formatDuration(trip.durationMin != null ? trip.durationMin * 60 : null)}
          </span>
          <span className="flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5" /> {trip.membersCount} members
          </span>
          <span className="flex items-center gap-1.5">
            <BellRing className="w-3.5 h-3.5" /> {formatCount(trip.alertsCount)} alerts
          </span>
          <span className="flex items-center gap-1.5">
            <Navigation2 className="w-3.5 h-3.5" /> {formatCount(trip.routeDeviations)} deviation{trip.routeDeviations === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between sm:flex-col sm:items-end gap-2 sm:gap-3 sm:border-l sm:border-border sm:pl-5">
        <div className="text-left sm:text-right">
          <p className="text-[11px] text-muted-foreground">Safety Score</p>
          <p className={`text-xl font-bold ${trip.riskLevel ? LEVEL_COLOR[trip.riskLevel] : 'text-muted-foreground'}`}>
            {trip.safetyScore != null ? `${trip.safetyScore}%` : 'N/A'}
          </p>
        </div>
        <Link
          href={`/dashboard/trip-summary?id=${trip.id}`}
          className="flex items-center gap-1.5 text-sm font-semibold text-rally-blue hover:underline whitespace-nowrap"
        >
          View Trip <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
