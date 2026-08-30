'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Route, Clock, Users, BellRing, Navigation2, UsersRound, Octagon, Siren, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import RiskRing from '@/components/dashboard/RiskRing';
import TripReplayPlayer from '@/components/dashboard/TripReplayPlayer';
import { fetchTripSummary } from '@/lib/history/tripSummary';
import { formatDistance, formatDuration, formatCount } from '@/lib/format';
import { friendlyErrorMessage } from '@/lib/api/errors';
import type { TripSummary } from '@/lib/mock/types';

export default function TripSummaryPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-muted-foreground">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      }
    >
      <TripSummaryContent />
    </Suspense>
  );
}

function TripSummaryContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get('id');

  const [summary, setSummary] = useState<TripSummary | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchTripSummary(id)
      .then((s) => {
        if (!cancelled) setSummary(s);
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
        <p className="text-sm">Loading trip summary…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4 px-6 text-center">
        <AlertCircle className="w-8 h-8 text-red-400" />
        <h1 className="text-xl font-semibold text-foreground">Couldn&apos;t load this trip</h1>
        <p className="text-sm text-muted-foreground max-w-sm">{error}</p>
        <Link href="/dashboard/history" className="px-5 py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity">
          Back to Trip History
        </Link>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4 px-6 text-center">
        <h1 className="text-xl font-semibold text-foreground">No trip to summarize yet</h1>
        <p className="text-sm text-muted-foreground max-w-sm">Complete a Rally trip to see its summary here.</p>
        <Link href="/dashboard" className="px-5 py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const stats = [
    { label: 'Distance', value: formatDistance(summary.distanceKm != null ? summary.distanceKm * 1000 : null), icon: Route },
    { label: 'Duration', value: formatDuration(summary.durationMin != null ? summary.durationMin * 60 : null), icon: Clock },
    { label: 'Members', value: formatCount(summary.membersCount), icon: Users },
    { label: 'Alerts', value: formatCount(summary.alertsCount), icon: BellRing },
    { label: 'Route deviations', value: formatCount(summary.routeDeviations), icon: Navigation2 },
    { label: 'Separation events', value: formatCount(summary.separationEvents), icon: UsersRound },
    { label: 'Unexpected stops', value: formatCount(summary.unexpectedStops), icon: Octagon },
    { label: 'SOS', value: formatCount(summary.sosCount), icon: Siren },
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-12 md:py-16 space-y-8">
        <div className="text-center">
          <div className="w-14 h-14 rounded-full bg-emerald-400/10 border border-emerald-400/30 flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-7 h-7 text-emerald-400" />
          </div>
          <h1 className="text-2xl md:text-3xl font-semibold text-foreground">Trip Complete</h1>
          <p className="text-sm text-muted-foreground mt-1.5">Here&apos;s how your Rally went.</p>
          <p className="text-xs text-muted-foreground mt-1">{summary.groupName} · {summary.date}</p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {stats.map((s) => (
            <div key={s.label} className="rounded-2xl border border-border bg-card p-4">
              <s.icon className="w-4 h-4 text-muted-foreground mb-2" />
              <p className="text-lg font-bold text-foreground leading-none">{s.value}</p>
              <p className="text-[11px] text-muted-foreground mt-1.5">{s.label}</p>
            </div>
          ))}
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 flex flex-col items-center text-center">
          <p className="text-[11px] font-semibold text-muted-foreground tracking-wider mb-4">SAFETY SCORE</p>
          {summary.safetyScore != null && summary.riskLevel != null ? (
            <>
              <RiskRing risk={{ score: summary.safetyScore, level: summary.riskLevel }} size={128} />
              <p
                className="text-sm font-bold tracking-wide mt-4"
                style={{
                  color:
                    summary.riskLevel === 'LOW RISK' ? '#34D399' : summary.riskLevel === 'MODERATE RISK' ? '#FBBF24' : '#F87171',
                }}
              >
                {summary.riskLevel}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground py-6">Not enough data to compute a safety score.</p>
          )}
        </div>

        <div>
          <h2 className="text-sm font-semibold text-foreground mb-3">Trip Replay</h2>
          <TripReplayPlayer tripId={summary.id} />
        </div>

        <div className="grid sm:grid-cols-2 gap-6">
          <div className="rounded-2xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Key Events</h2>
            {summary.keyEvents.length === 0 ? (
              <p className="text-sm text-muted-foreground">No timeline events recorded.</p>
            ) : (
              <div className="space-y-4">
                {summary.keyEvents.map((event, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="flex flex-col items-center pt-1">
                      <span className="w-2 h-2 rounded-full bg-rally-blue shrink-0" />
                      {i < summary.keyEvents.length - 1 && <span className="w-px flex-1 bg-border mt-1" style={{ minHeight: 16 }} />}
                    </div>
                    <div className="min-w-0 pb-1">
                      <p className="text-sm text-foreground">{event.label}</p>
                      <p className="text-[11px] text-muted-foreground font-mono">{event.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Insights</h2>
            {summary.insights.length === 0 ? (
              <p className="text-sm text-muted-foreground">No insights available for this trip.</p>
            ) : (
              <div className="space-y-3">
                {summary.insights.map((insight, i) => (
                  <p key={i} className="text-sm text-muted-foreground leading-relaxed pl-3 border-l-2 border-rally-blue/40">
                    {insight}
                  </p>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Link
            href="/dashboard/history"
            className="w-full sm:w-auto text-center px-6 py-3 rounded-xl border border-border text-foreground text-sm font-semibold hover:bg-white/5 transition-colors"
          >
            View Full Trip
          </Link>
          <Link
            href="/dashboard"
            className="w-full sm:w-auto text-center px-6 py-3 rounded-xl bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
