'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { MapPin, Navigation, Navigation2, Clock, Route as RouteIcon, AlertTriangle, ShieldCheck, Flag, Loader2, Users } from 'lucide-react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import LiveMap from '@/components/map/LiveMap';
import ConfirmModal from '@/components/dashboard/ConfirmModal';
import { groupService } from '@/lib/mock/groupService';
import { useLocation } from '@/hooks/useLocation';
import type { Group } from '@/lib/mock/types';
import { supabase } from '@/lib/supabase';

// Mock function to format duration
const formatDuration = (min: number) => {
  if (min < 60) return `~${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `~${h} hr ${m} min`;
};

function TripContent({ group }: { group: Group }) {
  const router = useRouter();
  const { location, isTracking, error: locError } = useLocation();
  const [showEndModal, setShowEndModal] = useState(false);
  const [ending, setEnding] = useState(false);
  const [actualName, setActualName] = useState('User');

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user) {
        setActualName(user.user_metadata?.full_name || user.user_metadata?.name || 'User');
      }
    });
  }, []);

  const me = group.members.find((m) => m.isCurrentUser);

  const handleEndTrip = async () => {
    setEnding(true);
    await groupService.endTrip();
    router.push('/dashboard/history'); // Note: or trip-summary
  };

  const isActive = !group.paused;
  
  // Calculate mock elapsed/distance based on group
  const elapsedMin = Math.round((Date.now() - group.trip.startedAt) / 60000) || 0;
  
  const renderGpsState = () => {
    if (locError) return { text: 'GPS Unavailable', color: 'text-red-400', dot: 'bg-red-400' };
    if (isTracking && location) {
      if (location.accuracy > 50) return { text: 'Poor Accuracy', color: 'text-orange-400', dot: 'bg-orange-400' };
      return { text: 'Tracking', color: 'text-emerald-400', dot: 'bg-emerald-400' };
    }
    if (isTracking && !location) return { text: 'Waiting for GPS', color: 'text-yellow-400', dot: 'bg-yellow-400 animate-pulse' };
    return { text: 'GPS Off', color: 'text-muted-foreground', dot: 'bg-muted-foreground' };
  };

  const gpsInfo = renderGpsState();

  return (
    <div className="min-h-screen flex flex-col h-screen overflow-hidden bg-background">
      <Topbar group={group} gpsState={isTracking ? (location ? 'active' : 'waiting') : (locError ? 'unavailable' : 'off')} />

      <div className="flex-1 p-4 md:p-6 flex flex-col gap-6 overflow-y-auto">
        
        {/* Header */}
        <div className="flex items-center justify-between shrink-0">
          <h1 className="text-2xl font-semibold text-foreground">Live Trip</h1>
          <div className="px-3 py-1.5 rounded-full bg-card border border-border flex items-center gap-1.5 text-xs font-semibold">
            {isActive ? (
              <><span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> <span className="text-emerald-400">Trip Active</span></>
            ) : (
              <><span className="w-2 h-2 rounded-full bg-muted-foreground" /> <span className="text-muted-foreground">Trip Not Active</span></>
            )}
          </div>
        </div>

        {/* Responsive layout */}
        <div className="flex flex-col lg:flex-row gap-6 flex-1 min-h-0">
          
          {/* Map Section */}
          <div className="lg:w-2/3 h-[50vh] lg:h-full min-h-[400px] shrink-0 lg:shrink rounded-2xl overflow-hidden border border-border bg-card">
            {locError && (
              <div className="absolute top-4 left-4 right-4 z-[1000] p-4 rounded-xl border border-red-500/30 bg-red-500/90 backdrop-blur-sm text-white shadow-lg flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 shrink-0" />
                <div className="text-sm">
                  <p className="font-semibold mb-1">Location access denied</p>
                  <p className="opacity-90">Location access is required for live tracking. Enable location access in your browser settings.</p>
                </div>
              </div>
            )}
            <LiveMap 
              group={group} 
              routeAlternatives={group.route && group.route.length > 0 ? [{ id: 'active', coordinates: group.route, selected: true }] : undefined}
            />
          </div>

          {/* Status Cards */}
          <div className="lg:w-1/3 flex flex-col gap-4 overflow-y-auto pr-1 pb-1">
            
            {/* TRIP */}
            <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
              <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Trip</p>
              
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold text-foreground truncate">{group.name}</h3>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {group.destination ? (
                    <>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Destination</p>
                        <p className="text-sm font-medium text-foreground truncate">{group.destination}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Distance</p>
                        <p className="text-sm font-medium text-foreground">{group.trip.distanceKm} km</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Estimated time</p>
                        <p className="text-sm font-medium text-foreground">{formatDuration(group.trip.durationMin || 0)}</p>
                      </div>
                    </>
                  ) : (
                    <div className="col-span-2">
                      <p className="text-sm text-muted-foreground">No route selected</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* YOUR LOCATION */}
            <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
              <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Your Location</p>
              
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${gpsInfo.dot}`} />
                <span className={`text-sm font-semibold ${gpsInfo.color}`}>{gpsInfo.text}</span>
              </div>

              {location ? (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Accuracy</p>
                    <p className="text-sm font-medium text-foreground">±{Math.round(location.accuracy)}m</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Speed</p>
                    <p className="text-sm font-medium text-foreground">{(location.speed || 0).toFixed(1)} m/s</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Location unavailable.</p>
              )}
            </div>

            {/* GROUP */}
            <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
              <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Group</p>
              
              <div className="flex items-center gap-2 text-sm text-foreground font-medium mb-2">
                <Users className="w-4 h-4 text-muted-foreground" />
                {group.members.length} {group.members.length === 1 ? 'member' : 'members'}
              </div>

              {me && (
                <div className="flex items-center gap-3">
                  <div className="relative shrink-0">
                    <div className="w-8 h-8 rounded-full bg-rally-blue/15 border border-rally-blue/30 text-rally-blue font-bold flex items-center justify-center text-xs">
                      {actualName.charAt(0)}
                    </div>
                    <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-card bg-emerald-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{actualName} <span className="text-muted-foreground text-xs ml-1">(You)</span></p>
                  </div>
                </div>
              )}
            </div>

            {/* SAFETY */}
            <div className="rounded-2xl border border-border bg-card p-5 space-y-3">
              <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Safety</p>
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-400/10 border border-emerald-400/30 flex items-center justify-center text-emerald-400 shrink-0">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">No active alerts</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Your RALLY is currently active.</p>
                </div>
              </div>
            </div>

            {/* END TRIP */}
            <button
              onClick={() => setShowEndModal(true)}
              className="mt-2 w-full flex items-center justify-center gap-2 px-4 py-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-bold hover:bg-red-500/20 transition-colors"
            >
              <Flag className="w-4 h-4" /> End Trip
            </button>

          </div>
        </div>

      </div>

      {showEndModal && (
        <ConfirmModal
          icon={Flag}
          title="End this trip?"
          description="Are you sure you want to end the current RALLY trip?"
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

export default function ActiveTripPage() {
  return (
    <RequireGroup>
      {(group) => {
        // STATE: TRIP NOT ACTIVE
        if (group.paused && group.trip.distanceKm === 0) {
          // Conceptually, if trip is paused/not active at start. 
          // Let's assume paused means inactive for now.
          return (
            <div className="min-h-screen flex flex-col bg-background">
              <Topbar group={group} gpsState="off" />
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto">
                <div className="w-16 h-16 rounded-2xl bg-rally-blue/10 flex items-center justify-center mb-6">
                  <Navigation className="w-8 h-8 text-rally-blue" />
                </div>
                <h1 className="text-2xl font-bold text-foreground mb-3">No active trip</h1>
                <p className="text-muted-foreground mb-8 text-sm">
                  Create/select a route and start a trip to see live tracking here.
                </p>
                <button
                  onClick={() => window.location.href = '/dashboard/route'}
                  className="px-6 py-3 rounded-xl bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity w-full"
                >
                  Go to Route
                </button>
              </div>
            </div>
          );
        }
        
        return <TripContent group={group} />;
      }}
    </RequireGroup>
  );
}
