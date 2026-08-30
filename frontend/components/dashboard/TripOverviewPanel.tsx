'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Navigation, Users, BellRing, Map, Flag, ArrowRight } from 'lucide-react';
import type { Group } from '@/lib/mock/types';
import ConfirmModal from './ConfirmModal';
import { groupService } from '@/lib/group/groupService';
import { friendlyErrorMessage } from '@/lib/api/errors';

export default function TripOverviewPanel({ group }: { group: Group }) {
  const router = useRouter();
  const [showEndModal, setShowEndModal] = useState(false);
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState<string | null>(null);

  const me = group.members.find((m) => m.isCurrentUser);
  const isLeader = me?.role === 'Leader';
  const onlineCount = group.members.filter((m) => m.online).length;

  const elapsedMin = Math.max(0, Math.round((Date.now() - group.trip.startedAt) / 60_000));
  const avgSpeed = elapsedMin > 0 ? Math.round((group.trip.distanceKm / elapsedMin) * 60) : 0;

  const handleEndTrip = async () => {
    setEnding(true);
    setEndError(null);
    try {
      const summary = await groupService.endTrip();
      router.push(`/dashboard/trip-summary?id=${summary.id}`);
    } catch (err) {
      setEndError(friendlyErrorMessage(err));
      setEnding(false);
    }
  };

  return (
    <div className="rounded-xl border border-white/10 bg-[#0A0A0C] p-5 space-y-5 flex flex-col justify-between h-full font-mono text-xs">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-[0.15em] text-white">
            TRIP OVERVIEW
          </h2>
          <span className="text-[11px] text-cyan-400 font-bold uppercase tracking-wider bg-cyan-400/10 border border-cyan-400/20 px-2 py-0.5 rounded-full">
            {group.destination}
          </span>
        </div>

        {/* Trip Stats Grid */}
        <div className="grid grid-cols-2 gap-2.5">
          <div className="p-3 rounded-lg bg-[#0B0C10] border border-white/5 space-y-1">
            <div className="text-[10px] text-white/40 uppercase tracking-wider">Elapsed Time</div>
            <div className="text-sm font-bold text-white">{elapsedMin} min</div>
          </div>
          <div className="p-3 rounded-lg bg-[#0B0C10] border border-white/5 space-y-1">
            <div className="text-[10px] text-white/40 uppercase tracking-wider">Distance</div>
            <div className="text-sm font-bold text-white">{group.trip.distanceKm} km</div>
          </div>
          <div className="p-3 rounded-lg bg-[#0B0C10] border border-white/5 space-y-1">
            <div className="text-[10px] text-white/40 uppercase tracking-wider">Avg Speed</div>
            <div className="text-sm font-bold text-white">{avgSpeed} km/h</div>
          </div>
          <div className="p-3 rounded-lg bg-[#0B0C10] border border-white/5 space-y-1">
            <div className="text-[10px] text-white/40 uppercase tracking-wider">Active Group</div>
            <div className="text-sm font-bold text-emerald-400">{onlineCount}/{group.members.length} Online</div>
          </div>
        </div>

        {/* Link */}
        <div>
          <Link
            href="/dashboard/trip"
            className="inline-flex items-center gap-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
          >
            <span>View live trip stream</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* Operational Quick Actions */}
      <div className="pt-4 border-t border-white/10 space-y-2.5">
        <div className="text-[10px] text-white/40 uppercase tracking-widest font-bold">
          QUICK ACTIONS
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Link
            href="/dashboard/trip"
            className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 text-white font-medium flex items-center justify-center gap-1.5 transition-colors"
          >
            <Navigation className="w-3.5 h-3.5 text-cyan-400" />
            <span>Live Trip</span>
          </Link>

          <Link
            href="/dashboard/members"
            className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 text-white font-medium flex items-center justify-center gap-1.5 transition-colors"
          >
            <Users className="w-3.5 h-3.5 text-emerald-400" />
            <span>Members</span>
          </Link>

          <Link
            href="/dashboard/alerts"
            className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 text-white font-medium flex items-center justify-center gap-1.5 transition-colors"
          >
            <BellRing className="w-3.5 h-3.5 text-amber-400" />
            <span>Alerts</span>
          </Link>

          <Link
            href="/dashboard/route"
            className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 text-white font-medium flex items-center justify-center gap-1.5 transition-colors"
          >
            <Map className="w-3.5 h-3.5 text-rally-blue" />
            <span>Route</span>
          </Link>
        </div>

        {isLeader && (
          <button
            onClick={() => setShowEndModal(true)}
            className="w-full mt-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 text-red-400 font-bold flex items-center justify-center gap-1.5 transition-colors"
          >
            <Flag className="w-3.5 h-3.5" />
            <span>End Rally Trip</span>
          </button>
        )}
      </div>

      {showEndModal && (
        <ConfirmModal
          icon={Flag}
          title="End this Rally trip?"
          description="This will end the trip for the whole group and generate a trip summary."
          confirmLabel="End Trip"
          busyLabel="Ending…"
          busy={ending}
          error={endError}
          onCancel={() => setShowEndModal(false)}
          onConfirm={handleEndTrip}
        />
      )}
    </div>
  );
}
