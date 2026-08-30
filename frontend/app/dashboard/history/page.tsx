'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Search, Compass, Loader2, AlertCircle } from 'lucide-react';
import Topbar from '@/components/dashboard/Topbar';
import TripHistoryCard, { type HistoryTripSummary } from '@/components/dashboard/TripHistoryCard';
import RequireAuth from '@/components/dashboard/RequireAuth';
import { useGroup } from '@/lib/group/useGroup';
import { listMyTripHistory } from '@/lib/api/trips';
import { friendlyErrorMessage } from '@/lib/api/errors';
import type { TripHistoryItem, TripStatus } from '@/lib/api/types';

type DateFilter = 'all' | 'week' | 'month';
type StatusFilter = 'all' | 'COMPLETED' | 'CANCELLED';

const PAGE_SIZE = 20;

function toHistorySummary(item: TripHistoryItem): HistoryTripSummary {
  const durationMin =
    item.started_at && item.ended_at
      ? Math.max(0, Math.round((new Date(item.ended_at).getTime() - new Date(item.started_at).getTime()) / 60_000))
      : null;
  return {
    id: item.trip_id,
    groupName: item.name ?? 'Rally trip',
    date: item.started_at
      ? new Date(item.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      : 'Unknown date',
    distanceKm: item.distance_meters != null ? item.distance_meters / 1000 : null,
    durationMin,
    membersCount: item.member_count,
    // Not available from the list endpoint — only per-trip analytics
    // computes these (see HistoryTripSummary's docstring).
    alertsCount: null,
    routeDeviations: null,
    safetyScore: null,
    riskLevel: null,
  };
}

export default function TripHistoryPage() {
  return (
    <RequireAuth>
      <TripHistoryContent />
    </RequireAuth>
  );
}

function TripHistoryContent() {
  const { group } = useGroup();
  const [search, setSearch] = useState('');
  const [dateFilter, setDateFilter] = useState<DateFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const [items, setItems] = useState<TripHistoryItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      setError(null);
      if (append) setLoadingMore(true);
      try {
        const from = dateFilter === 'all' ? undefined : new Date(Date.now() - (dateFilter === 'week' ? 7 : 30) * 86_400_000).toISOString();
        const response = await listMyTripHistory({
          status: statusFilter === 'all' ? undefined : (statusFilter as TripStatus),
          from,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setItems((prev) => (append && prev ? [...prev, ...response.items] : response.items));
        setTotal(response.total);
        setOffset(nextOffset);
      } catch (err) {
        setError(friendlyErrorMessage(err));
        if (!append) setItems([]);
      } finally {
        setLoadingMore(false);
      }
    },
    [dateFilter, statusFilter]
  );

  useEffect(() => {
    void load(0, false);
    // Re-run whenever the filters change; intentionally not depending on
    // `load`'s identity beyond dateFilter/statusFilter (see its own deps).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFilter, statusFilter]);

  if (items === null) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
        <p className="text-sm">Loading trip history…</p>
      </div>
    );
  }

  const summaries = items.map(toHistorySummary);
  const filtered = summaries.filter((trip) => !search || trip.groupName.toLowerCase().includes(search.toLowerCase()));
  const hasMore = items.length < total;

  return (
    <div className="min-h-screen flex flex-col">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 space-y-6 max-w-4xl">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Trip History</h1>
          <p className="text-sm text-muted-foreground mt-1">{total} trip{total === 1 ? '' : 's'} recorded</p>
        </div>

        {error && (
          <p className="flex items-center gap-2 text-sm text-red-400">
            <AlertCircle className="w-4 h-4 shrink-0" /> {error}
          </p>
        )}

        {(total > 0 || search || dateFilter !== 'all' || statusFilter !== 'all') && (
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
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              className="bg-card border border-border rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-rally-blue transition-colors"
            >
              <option value="all">All statuses</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </div>
        )}

        {total === 0 ? (
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
          <>
            <div className="space-y-3">
              {filtered.map((trip) => (
                <TripHistoryCard key={trip.id} trip={trip} />
              ))}
            </div>
            {hasMore && !search && (
              <button
                onClick={() => void load(offset + PAGE_SIZE, true)}
                disabled={loadingMore}
                className="w-full py-2.5 rounded-lg border border-border text-sm font-semibold text-foreground hover:bg-white/5 transition-colors disabled:opacity-60"
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
