'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Search, Compass, Loader2 } from 'lucide-react';
import Topbar from '@/components/dashboard/Topbar';
import TripHistoryCard from '@/components/dashboard/TripHistoryCard';
import { useGroup } from '@/lib/mock/useGroup';
import { getTripHistory } from '@/lib/mock/tripHistoryService';
import type { TripSummary } from '@/lib/mock/types';

type DateFilter = 'all' | 'week' | 'month';
type ScoreFilter = 'all' | 'low' | 'moderate' | 'high';

export default function TripHistoryPage() {
  const { group } = useGroup();
  const [search, setSearch] = useState('');
  const [dateFilter, setDateFilter] = useState<DateFilter>('all');
  const [scoreFilter, setScoreFilter] = useState<ScoreFilter>('all');

  // Starts null on both server and client — the trip history store reads
  // localStorage synchronously, so reading it during render (even in a
  // client-only useMemo) would mismatch the server's render. Load in effect.
  const [allTrips, setAllTrips] = useState<TripSummary[] | null>(null);

  useEffect(() => {
    setAllTrips(getTripHistory());
  }, []);

  if (allTrips === null) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
        <p className="text-sm">Loading trip history…</p>
      </div>
    );
  }

  const filtered = allTrips.filter((trip) => {
    if (search && !trip.groupName.toLowerCase().includes(search.toLowerCase())) return false;

    if (dateFilter !== 'all') {
      const days = dateFilter === 'week' ? 7 : 30;
      const ageDays = (Date.now() - trip.completedAt) / (1000 * 60 * 60 * 24);
      if (ageDays > days) return false;
    }

    if (scoreFilter === 'low' && trip.riskLevel !== 'HIGH RISK') return false;
    if (scoreFilter === 'moderate' && trip.riskLevel !== 'MODERATE RISK') return false;
    if (scoreFilter === 'high' && trip.riskLevel !== 'LOW RISK') return false;

    return true;
  });

  return (
    <div className="min-h-screen flex flex-col">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 space-y-6 max-w-4xl">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Trip History</h1>
          <p className="text-sm text-muted-foreground mt-1">{allTrips.length} trip{allTrips.length === 1 ? '' : 's'} recorded</p>
        </div>

        {allTrips.length > 0 && (
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search trips…"
                className="w-full bg-card border border-border rounded-xl pl-10 pr-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-rally-blue transition-colors"
              />
            </div>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value as DateFilter)}
              className="bg-card border border-border rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-rally-blue transition-colors"
            >
              <option value="all">All time</option>
              <option value="week">Last 7 days</option>
              <option value="month">Last 30 days</option>
            </select>
            <select
              value={scoreFilter}
              onChange={(e) => setScoreFilter(e.target.value as ScoreFilter)}
              className="bg-card border border-border rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-rally-blue transition-colors"
            >
              <option value="all">All safety scores</option>
              <option value="high">Low risk</option>
              <option value="moderate">Moderate risk</option>
              <option value="low">High risk</option>
            </select>
          </div>
        )}

        {allTrips.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center gap-4 rounded-2xl border border-border bg-card">
            <div className="w-12 h-12 rounded-2xl bg-rally-blue/10 border border-rally-blue/30 flex items-center justify-center text-rally-blue">
              <Compass className="w-6 h-6" />
            </div>
            <div>
              <p className="text-base font-semibold text-foreground">No trips yet</p>
              <p className="text-sm text-muted-foreground mt-1">Start your first Rally journey.</p>
            </div>
            <Link
              href="/create-group"
              className="px-5 py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
            >
              Create a Rally
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-2 rounded-2xl border border-border bg-card">
            <p className="text-sm text-muted-foreground">No trips match these filters.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((trip) => (
              <TripHistoryCard key={trip.id} trip={trip} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
