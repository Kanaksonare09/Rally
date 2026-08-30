import React, { useEffect } from 'react';
import { useLocation, getLocationQuality } from '@/hooks/useLocation';
import { Play, Square, AlertTriangle, CheckCircle2, Crosshair, MapPin } from 'lucide-react';
import { groupService } from '@/lib/mock/groupService';

export default function LocationCard() {
  const { location, isTracking, error, permissionState, startTracking, stopTracking } = useLocation();

  // Wire it up to our backend group service when location changes!
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
    <div className="bg-card border border-border rounded-2xl p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-foreground flex items-center gap-2">
          <MapPin className="w-4 h-4 text-rally-blue" />
          Location Status
        </h3>
        <div className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-white/5 border border-border">
          {isTracking ? (
            <>
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-400">Tracking</span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 rounded-full bg-muted-foreground" />
              <span className="text-muted-foreground">Not Tracking</span>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {location && isTracking && (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="p-3 rounded-xl bg-background/50 border border-border">
            <span className="text-muted-foreground text-xs font-medium block mb-0.5">Latitude</span>
            <span className="font-mono text-foreground">{location.latitude.toFixed(6)}</span>
          </div>
          <div className="p-3 rounded-xl bg-background/50 border border-border">
            <span className="text-muted-foreground text-xs font-medium block mb-0.5">Longitude</span>
            <span className="font-mono text-foreground">{location.longitude.toFixed(6)}</span>
          </div>
          <div className="p-3 rounded-xl bg-background/50 border border-border">
            <span className="text-muted-foreground text-xs font-medium block mb-0.5">Accuracy</span>
            <span className="text-foreground">±{Math.round(location.accuracy)}m ({quality})</span>
          </div>
          <div className="p-3 rounded-xl bg-background/50 border border-border">
            <span className="text-muted-foreground text-xs font-medium block mb-0.5">Speed</span>
            <span className="text-foreground">{location.speed ? `${location.speed.toFixed(1)} m/s` : 'Unavailable'}</span>
          </div>
        </div>
      )}

      <button
        onClick={isTracking ? stopTracking : startTracking}
        className={`w-full py-2.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-colors ${
          isTracking 
            ? 'bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/20' 
            : 'bg-rally-blue text-white hover:bg-rally-blue/90'
        }`}
      >
        {isTracking ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        {isTracking ? 'Stop Tracking' : 'Start Tracking'}
      </button>
    </div>
  );
}
