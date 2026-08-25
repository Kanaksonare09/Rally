'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Route, Clock, Gauge, Users, Pause, Play, Flag } from 'lucide-react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import GroupHealthCard from '@/components/dashboard/GroupHealthCard';
import ActivityFeed from '@/components/dashboard/ActivityFeed';
import ConfirmModal from '@/components/dashboard/ConfirmModal';
import SosButton from '@/components/dashboard/SosButton';
import LiveMap from '@/components/map/LiveMap';
import { groupService } from '@/lib/mock/groupService';
import type { Group } from '@/lib/mock/types';

function useElapsedMinutes(startedAt: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(interval);
  }, []);
  return Math.max(0, Math.round((now - startedAt) / 60_000));
}

export default function ActiveTripPage() {
  return <RequireGroup>{(group) => <TripContent group={group} />}</RequireGroup>;
}

function TripContent({ group }: { group: Group }) {
  const router = useRouter();
  const [showEndModal, setShowEndModal] = useState(false);
  const [ending, setEnding] = useState(false);
  const elapsedMin = useElapsedMinutes(group.trip.startedAt);
  const avgSpeed = elapsedMin > 0 ? Math.round((group.trip.distanceKm / elapsedMin) * 60) : 0;
  const onlineCount = group.members.filter((m) => m.online).length;

  const handleEndTrip = async () => {
    setEnding(true);
    await groupService.endTrip();
    router.push('/dashboard/trip-summary');
  };

  const handleTogglePause = () => {
    if (group.paused) groupService.resumeTrip();
    else groupService.pauseTrip();
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <span
              className={`inline-flex items-center gap-1.5 text-[11px] font-bold tracking-wide px-2.5 py-1 rounded-full border mb-2 ${
                group.paused
                  ? 'bg-amber-400/10 border-amber-400/30 text-amber-400'
                  : 'bg-emerald-400/10 border-emerald-400/30 text-emerald-400'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${group.paused ? 'bg-amber-400' : 'bg-emerald-400 animate-pulse'}`} />
              {group.paused ? 'PAUSED' : 'LIVE TRIP'}
            </span>
            <h1 className="text-xl font-semibold text-foreground">{group.name}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Started: {elapsedMin} minutes ago</p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={handleTogglePause}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border text-sm font-semibold text-foreground hover:bg-white/5 transition-colors"
            >
              {group.paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
              {group.paused ? 'Resume Trip' : 'Pause Trip'}
            </button>
            <Link
              href="/dashboard/members"
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-border text-sm font-semibold text-foreground hover:bg-white/5 transition-colors"
            >
              <Users className="w-4 h-4" /> View Members
            </Link>
            <button
              onClick={() => setShowEndModal(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-semibold hover:bg-red-500/20 transition-colors"
            >
              <Flag className="w-4 h-4" /> End Trip
            </button>
          </div>
        </div>

        <div className="relative h-[55vh] min-h-[380px]">
          <LiveMap group={group} showStart />
          <div className="absolute top-4 left-4 z-[999]">
            <GroupHealthCard group={group} />
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Distance', value: `${group.trip.distanceKm} km`, icon: Route },
            { label: 'Duration', value: `${elapsedMin} min`, icon: Clock },
            { label: 'Average Speed', value: `${avgSpeed} km/h`, icon: Gauge },
            { label: 'Members', value: `${onlineCount}/${group.members.length}`, icon: Users },
          ].map((s) => (
            <div key={s.label} className="rounded-2xl border border-border bg-card p-4">
              <s.icon className="w-4 h-4 text-muted-foreground mb-2" />
              <p className="text-lg font-bold text-foreground leading-none">{s.value}</p>
              <p className="text-[11px] text-muted-foreground mt-1.5">{s.label}</p>
            </div>
          ))}
        </div>

        <ActivityFeed members={group.members} />
      </div>

      <SosButton />

      {showEndModal && (
        <ConfirmModal
          icon={Flag}
          title="End this Rally trip?"
          description="This will end the trip for the whole group and take you to a trip summary."
          confirmLabel="End Trip"
          busyLabel="Ending…"
          busy={ending}
          onCancel={() => setShowEndModal(false)}
          onConfirm={handleEndTrip}
        />
      )}
    </div>
  );
}
