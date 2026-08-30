'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Search, Compass, Loader2 } from 'lucide-react';
import Topbar from '@/components/dashboard/Topbar';
import { useGroup } from '@/lib/mock/useGroup';
import { getTripHistory } from '@/lib/mock/tripHistoryService';
import type { TripSummary } from '@/lib/mock/types';

export default function TripHistoryPage() {
  const { group } = useGroup();
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'All' | 'Completed' | 'Cancelled'>('All');

  // Load trips in effect to avoid hydration mismatch
  const [allTrips, setAllTrips] = useState<TripSummary[] | null>(null);

  useEffect(() => {
    setAllTrips(getTripHistory());
  }, []);

  if (allTrips === null) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-muted-foreground bg-background">
        <Loader2 className="w-6 h-6 animate-spin" />
        <p className="text-sm">Loading trip history…</p>
      </div>
    );
  }

  const filtered = allTrips.filter((trip) => {
    if (search && !trip.groupName.toLowerCase().includes(search.toLowerCase()) && !trip.destination.toLowerCase().includes(search.toLowerCase())) return false;
    // Since mock doesn't currently support cancelled trips natively, we assume all are Completed
    // If the data model adds a status field, we would filter here.
    if (filter === 'Completed') return true; // assuming all are completed for now
    if (filter === 'Cancelled') return false; // no cancelled trips yet
    return true;
  });

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 lg:p-8 space-y-6 max-w-4xl mx-auto w-full">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Trip History</h1>
          <p className="text-sm text-muted-foreground mt-1">Review your previous RALLY journeys</p>
        </div>

        {allTrips.length > 0 && (
          <p className="text-sm font-semibold text-foreground">{allTrips.length} completed trips</p>
        )}

        {/* Active Trip Notice */}
        {group && !group.paused && (
          <div className="flex items-center justify-between p-4 rounded-xl border border-rally-blue/30 bg-rally-blue/10 text-rally-blue">
            <span className="text-sm font-semibold flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rally-blue animate-pulse" />
              Trip currently active
            </span>
            <Link
              href="/dashboard/trip"
              className="px-3 py-1.5 rounded-lg bg-rally-blue text-white text-xs font-bold hover:bg-rally-blue/90 transition-colors"
            >
              View Live Trip
            </Link>
          </div>
        )}

        {/* Search & Filters */}
        {allTrips.length > 0 && (
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="🔍 Search trips..."
                className="w-full bg-card border border-border rounded-xl pl-10 pr-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-border transition-colors"
              />
            </div>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as any)}
              className="bg-card border border-border rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-border transition-colors appearance-none pr-8 cursor-pointer relative"
              style={{ backgroundImage: 'url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%239ca3af%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px top 50%', backgroundSize: '10px auto' }}
            >
              <option value="All">All</option>
              <option value="Completed">Completed</option>
              <option value="Cancelled">Cancelled</option>
            </select>
          </div>
        )}

        {/* List */}
        {allTrips.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center gap-4 rounded-2xl border border-border bg-card">
            <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-muted-foreground">
              <Compass className="w-6 h-6" />
            </div>
            <div>
              <p className="text-base font-semibold text-foreground">No trips yet</p>
              <p className="text-sm text-muted-foreground mt-1">Complete your first RALLY trip<br/>to see your journey history here.</p>
            </div>
            <Link
              href="/dashboard/route"
              className="px-5 py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
            >
              Plan a Trip
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-2 rounded-2xl border border-border bg-card">
            <p className="text-sm text-foreground font-semibold">No trips found</p>
            <p className="text-sm text-muted-foreground">Try another RALLY name or destination.</p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase px-2">Trips</p>
            {filtered.map((trip) => {
              const h = Math.floor(trip.durationMin / 60);
              const m = trip.durationMin % 60;
              const durationStr = h > 0 ? `${h}h ${m}m` : `${m} min`;

              return (
                <div key={trip.id} className="rounded-2xl border border-border bg-card p-5 hover:border-border/80 transition-colors flex flex-col gap-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-base font-semibold text-foreground">{trip.groupName}</h3>
                      <p className="text-sm text-muted-foreground mt-0.5">{trip.date}</p>
                    </div>
                    <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 bg-emerald-400/10 px-2.5 py-1 rounded-md">
                      🟢 Completed
                    </span>
                  </div>

                  {trip.destination && (
                    <div className="text-sm text-foreground flex items-center gap-2">
                      📍 {trip.destination}
                    </div>
                  )}

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mt-2">
                    <div className="text-sm text-muted-foreground font-medium flex items-center flex-wrap gap-2">
                      <span>{trip.distanceKm} km</span>
                      <span>·</span>
                      <span>{durationStr}</span>
                      <span>·</span>
                      <span>{trip.membersCount} members</span>
                    </div>
                    
                    <Link
                      href={`/dashboard/history/${trip.id}`}
                      className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-xs font-semibold hover:bg-white/10 transition-colors shrink-0"
                    >
                      View Details
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
