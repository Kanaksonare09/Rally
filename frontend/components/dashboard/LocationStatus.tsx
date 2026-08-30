'use client';

import { useLocation, getLocationQuality } from '@/hooks/useLocation';
import { Play, Square, MapPin } from 'lucide-react';
import { groupService } from '@/lib/mock/groupService';
import { useEffect } from 'react';

export default function LocationStatus() {
  const { location, isTracking, error, permissionState, startTracking, stopTracking } = useLocation();

  // Wire GPS to backend group service
  useEffect(() => {
    if (location && isTracking) {
      groupService.updateMyPosition(
        location.latitude,
        location.longitude,
        location.speed,
        location.heading
      );
    }
  }, [location, isTracking]);

  const quality = getLocationQuality(location?.accuracy);

  return (
    <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em]">LOCATION</p>
        <div className="flex items-center gap-1.5 text-xs font-semibold">
          {isTracking ? (
            <>
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-400">Tracking</span>
            </>
          ) : (
            <>
              <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground" />
              <span className="text-muted-foreground">Not Tracking</span>
            </>
          )}
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5">{error}</p>
      )}

      {location && isTracking && (
        <div className="grid grid-cols-2 gap-2.5 text-sm">
          <div className="p-2.5 rounded-lg bg-background/50 border border-border">
            <span className="text-muted-foreground text-[10px] font-medium block mb-0.5">Latitude</span>
            <span className="font-mono text-foreground text-xs">{location.latitude.toFixed(6)}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-background/50 border border-border">
            <span className="text-muted-foreground text-[10px] font-medium block mb-0.5">Longitude</span>
            <span className="font-mono text-foreground text-xs">{location.longitude.toFixed(6)}</span>
          </div>
          <div className="p-2.5 rounded-lg bg-background/50 border border-border">
            <span className="text-muted-foreground text-[10px] font-medium block mb-0.5">Accuracy</span>
            <span className="text-foreground text-xs">±{Math.round(location.accuracy)}m ({quality})</span>
          </div>
          <div className="p-2.5 rounded-lg bg-background/50 border border-border">
            <span className="text-muted-foreground text-[10px] font-medium block mb-0.5">Speed</span>
            <span className="text-foreground text-xs">
              {location.speed ? `${location.speed.toFixed(1)} m/s` : 'Unavailable'}
            </span>
          </div>
        </div>
      )}

      <button
        onClick={isTracking ? stopTracking : startTracking}
        className={`w-full py-2.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-colors ${
          isTracking
            ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20'
            : 'bg-rally-blue text-white hover:bg-rally-blue/90'
        }`}
      >
        {isTracking ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        {isTracking ? 'Stop Tracking' : 'Start Tracking'}
      </button>
    </div>
  );
}
