'use client';

import { useState } from 'react';
import { useGroup } from '@/lib/mock/useGroup';
import { useLocation } from '@/hooks/useLocation';
import Topbar from '@/components/dashboard/Topbar';
import EmptyRallyState from '@/components/dashboard/EmptyRallyState';
import RallyOverview from '@/components/dashboard/RallyOverview';
import LocationStatus from '@/components/dashboard/LocationStatus';
import MemberList from '@/components/dashboard/MemberList';
import LiveMap from '@/components/map/LiveMap';
import { ShieldCheck } from 'lucide-react';

export default function DashboardPage() {
  const { group, loading } = useGroup();
  const [tripStarted, setTripStarted] = useState(false);
  const { isTracking } = useLocation();

  if (loading) {
    return <div className="min-h-screen bg-background" />;
  }

  // STATE 1 — No RALLY
  if (!group) {
    return (
      <div className="min-h-screen flex flex-col">
        <Topbar group={null} />
        <div className="flex-1 flex flex-col justify-center items-center">
          <EmptyRallyState />
        </div>
      </div>
    );
  }

  // STATE 2 — RALLY exists, but no active trip
  if (!tripStarted) {
    return (
      <div className="min-h-screen flex flex-col">
        <Topbar group={group} gpsState={isTracking ? 'active' : 'off'} />
        <div className="flex-1 p-4 md:p-6 lg:p-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 max-w-7xl mx-auto">
            <RallyOverview group={group} onStartTrip={() => setTripStarted(true)} />
            <LocationStatus />
            <div className="flex flex-col gap-5">
              <MemberList members={group.members} />
              
              {/* Safety Placeholder */}
              <div className="rounded-2xl border border-border bg-card p-5 space-y-3">
                <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em]">SAFETY</p>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-400/10 border border-emerald-400/30 flex items-center justify-center text-emerald-400">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">No active alerts</p>
                    <p className="text-xs text-muted-foreground">Your RALLY is ready.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // STATE 3 — Active trip
  return (
    <div className="min-h-screen flex flex-col h-screen overflow-hidden">
      <Topbar group={group} gpsState={isTracking ? 'active' : 'off'} />
      <div className="flex-1 p-4 md:p-6 flex flex-col gap-5 min-h-0 overflow-y-auto">
        <div className="relative flex-none h-[50vh] md:h-[65vh] shrink-0">
          <LiveMap group={group} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 flex-none pb-8">
          <LocationStatus />
          <RallyOverview group={group} />
        </div>
      </div>
    </div>
  );
}
