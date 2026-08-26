'use client';

import React from 'react';
import { Route, Clock, Gauge, Users } from 'lucide-react';
import type { TripStats } from '@/lib/mock/types';

export default function MapTelemetryBar({
  trip,
  onlineCount,
  totalMembers,
}: {
  trip: TripStats;
  onlineCount: number;
  totalMembers: number;
}) {
  const hours = Math.floor(trip.durationMin / 60);
  const mins = trip.durationMin % 60;
  const durationText = hours > 0 ? `${hours}h ${mins}m` : `${mins} min`;
  const avgSpeed = trip.durationMin > 0 ? Math.round((trip.distanceKm / trip.durationMin) * 60) : 0;

  return (
    <div className="rounded-xl border border-white/15 bg-[#0A0A0C]/90 backdrop-blur-md px-4 py-2.5 shadow-2xl flex flex-wrap items-center justify-between gap-4 font-mono text-xs text-white">
      {/* Distance */}
      <div className="flex items-center gap-2">
        <Route className="w-3.5 h-3.5 text-rally-blue" />
        <span className="text-white/50 text-[11px] uppercase tracking-wider">Distance</span>
        <span className="font-bold text-white ml-0.5">{trip.distanceKm} km</span>
      </div>

      <div className="w-px h-3.5 bg-white/10 hidden sm:block" />

      {/* Duration */}
      <div className="flex items-center gap-2">
        <Clock className="w-3.5 h-3.5 text-cyan-400" />
        <span className="text-white/50 text-[11px] uppercase tracking-wider">Duration</span>
        <span className="font-bold text-white ml-0.5">{durationText}</span>
      </div>

      <div className="w-px h-3.5 bg-white/10 hidden sm:block" />

      {/* Speed */}
      <div className="flex items-center gap-2">
        <Gauge className="w-3.5 h-3.5 text-emerald-400" />
        <span className="text-white/50 text-[11px] uppercase tracking-wider">Avg Speed</span>
        <span className="font-bold text-white ml-0.5">{avgSpeed} km/h</span>
      </div>

      <div className="w-px h-3.5 bg-white/10 hidden sm:block" />

      {/* Members */}
      <div className="flex items-center gap-2">
        <Users className="w-3.5 h-3.5 text-amber-400" />
        <span className="text-white/50 text-[11px] uppercase tracking-wider">Members</span>
        <span className="font-bold text-white ml-0.5">
          {onlineCount}/{totalMembers} <span className="text-emerald-400 font-medium text-[10px]">ONLINE</span>
        </span>
      </div>
    </div>
  );
}
