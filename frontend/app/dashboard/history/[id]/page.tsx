'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Loader2 } from 'lucide-react';
import RouteReplayMap from '@/components/map/RouteReplayMap';
import { getTripSummaryById } from '@/lib/mock/tripHistoryService';
import type { TripSummary } from '@/lib/mock/types';
import Topbar from '@/components/dashboard/Topbar';
import { useGroup } from '@/lib/mock/useGroup';

export default function TripDetailsPage() {
  const { id } = useParams();
  const { group } = useGroup();
  
  const [trip, setTrip] = useState<TripSummary | null | undefined>(undefined);

  useEffect(() => {
    if (typeof id === 'string') {
      const summary = getTripSummaryById(id);
      setTrip(summary);
    }
  }, [id]);

  if (trip === undefined) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-muted-foreground bg-background">
        <Loader2 className="w-6 h-6 animate-spin" />
        <p className="text-sm">Loading trip details…</p>
      </div>
    );
  }

  if (trip === null) {
    return (
      <div className="min-h-screen bg-background flex flex-col">
        <Topbar group={group} />
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center max-w-md mx-auto">
          <h1 className="text-xl font-semibold text-foreground">Trip not found</h1>
          <p className="text-sm text-muted-foreground">You don't have access to this trip, or it doesn't exist.</p>
          <Link href="/dashboard/history" className="px-5 py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity">
            Back to Trip History
          </Link>
        </div>
      </div>
    );
  }

  const h = Math.floor(trip.durationMin / 60);
  const m = trip.durationMin % 60;
  const durationStr = h > 0 ? `${h}h ${m}m` : `${m} min`;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Topbar group={group} />
      
      <div className="flex-1 p-4 md:p-6 lg:p-8 space-y-6 max-w-4xl mx-auto w-full">
        {/* Navigation */}
        <Link 
          href="/dashboard/history" 
          className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Trip History
        </Link>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{trip.groupName}</h1>
            <p className="text-sm text-muted-foreground mt-1">{trip.date}</p>
          </div>
          <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 bg-emerald-400/10 px-2.5 py-1 rounded-md shrink-0">
            🟢 Completed
          </span>
        </div>

        {/* Map */}
        <div className="rounded-2xl border border-border bg-card p-4 sm:p-6 flex flex-col">
          <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-4">Map</p>
          {trip.route && trip.route.length > 0 ? (
            <div className="h-[300px] sm:h-[400px]">
              <RouteReplayMap summary={trip} />
            </div>
          ) : (
            <div className="h-[300px] sm:h-[400px] rounded-2xl border border-border bg-background flex items-center justify-center text-muted-foreground text-sm font-medium">
              Route data unavailable for this trip.
            </div>
          )}
        </div>

        {/* Trip Summary */}
        <div className="rounded-2xl border border-border bg-card p-4 sm:p-6 grid grid-cols-2 gap-y-6 gap-x-4">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-1">Distance</p>
            <p className="text-xl font-bold text-foreground">{trip.distanceKm} km</p>
          </div>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-1">Duration</p>
            <p className="text-xl font-bold text-foreground">{durationStr}</p>
          </div>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-1">Destination</p>
            <p className="text-xl font-bold text-foreground">{trip.destination || 'N/A'}</p>
          </div>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-1">Members</p>
            <p className="text-xl font-bold text-foreground">{trip.membersCount}</p>
          </div>
        </div>

        {/* Future Insights Section */}
        <div className="rounded-2xl border border-border bg-card p-4 sm:p-6 text-center">
          <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-2">Trip Insights</p>
          <p className="text-sm text-muted-foreground">Analytics will appear here once enough trip data has been collected.</p>
        </div>
      </div>
    </div>
  );
}
