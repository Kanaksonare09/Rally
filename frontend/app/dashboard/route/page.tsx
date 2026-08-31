'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Map as MapIcon, Loader2, Navigation, AlertTriangle, ArrowRight, Edit2, Check } from 'lucide-react';
import Topbar from '@/components/dashboard/Topbar';
import RequireGroup from '@/components/dashboard/RequireGroup';
import LiveMap from '@/components/map/LiveMap';
import { searchDestination, Destination } from '@/lib/services/geocoding';
import { calculateRoute, RouteOption } from '@/lib/services/routing';
import { groupService } from '@/lib/mock/groupService';

function useDeviceLocation() {
  const [loc, setLoc] = useState<{lat: number, lng: number} | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!('geolocation' in navigator)) {
      setLoc({ lat: 19.0760, lng: 72.8777 }); // Fallback
      setError(true);
      return;
    }
    
    let fallbackTimer = setTimeout(() => {
      if (!loc) {
        setLoc({ lat: 19.0760, lng: 72.8777 }); // Fallback to Mumbai if taking too long
        setError(true);
      }
    }, 4000);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        clearTimeout(fallbackTimer);
        setLoc({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setError(false);
      },
      () => {
        clearTimeout(fallbackTimer);
        setLoc({ lat: 19.0760, lng: 72.8777 });
        setError(true);
      },
      { enableHighAccuracy: true, timeout: 5000 }
    );
    
    return () => clearTimeout(fallbackTimer);
  }, []);

  return { loc, error };
}

export default function RoutePage() {
  const router = useRouter();
  const { loc: deviceLoc, error: locError } = useDeviceLocation();
  
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [suggestions, setSuggestions] = useState<Destination[]>([]);
  
  const [destination, setDestination] = useState<Destination | null>(null);
  
  const [isCalculating, setIsCalculating] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  
  const [routeAlternatives, setRouteAlternatives] = useState<RouteOption[]>([]);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);

  useEffect(() => {
    if (!query.trim() || destination) {
      setSuggestions([]);
      return;
    }
    
    const delay = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await searchDestination(query);
        setSuggestions(results);
      } catch (e) {
        console.error(e);
      } finally {
        setIsSearching(false);
      }
    }, 400);
    
    return () => clearTimeout(delay);
  }, [query, destination]);

  const handleSelectDestination = (dest: Destination) => {
    setDestination(dest);
    setQuery(dest.name);
    setSuggestions([]);
    setRouteError(null);
  };

  const handlePlanRoute = async () => {
    if (!deviceLoc) {
      setRouteError("Current location is unavailable.");
      return;
    }
    if (!destination) return;
    
    const distSq = Math.pow(deviceLoc.lat - destination.latitude, 2) + Math.pow(deviceLoc.lng - destination.longitude, 2);
    if (distSq < 0.00001) {
      setRouteError("You are already at the selected destination.");
      return;
    }

    setIsCalculating(true);
    setRouteError(null);
    setRouteAlternatives([]);
    setSelectedRouteId(null);
    try {
      const res = await calculateRoute(deviceLoc, { lat: destination.latitude, lng: destination.longitude });
      setRouteAlternatives(res);
      const recommended = res.find(r => r.isRecommended) || res[0];
      if (recommended) {
        setSelectedRouteId(recommended.id);
      }
    } catch (err: any) {
      setRouteError(err.message || 'We couldn\'t calculate a route. Please try again.');
    } finally {
      setIsCalculating(false);
    }
  };

  const formatDistance = (meters: number) => {
    if (meters < 1000) return `${meters.toFixed(0)} m`;
    return `${(meters / 1000).toFixed(1)} km`;
  };

  const formatDuration = (seconds: number) => {
    const m = Math.round(seconds / 60);
    if (m < 60) return `~${m} min`;
    const h = Math.floor(m / 60);
    const mRem = m % 60;
    return `~${h} hr ${mRem} min`;
  };

  const handleStartTrip = () => {
    const selectedRoute = routeAlternatives.find(r => r.id === selectedRouteId);
    if (selectedRoute && destination) {
      groupService.setTripRoute(
        destination.name,
        destination.latitude,
        destination.longitude,
        selectedRoute.coordinates,
        selectedRoute.distance,
        selectedRoute.duration
      );
      groupService.startTrip();
    }
    router.push('/dashboard/trip');
  };

  const handleChangeDestination = () => {
    setDestination(null);
    setRouteAlternatives([]);
    setSelectedRouteId(null);
    setQuery('');
  };

  const renderStatus = () => {
    if (routeAlternatives.length > 0) return <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400"><span className="w-2 h-2 rounded-full bg-emerald-400"></span> Routes Ready</span>;
    if (isCalculating) return <span className="flex items-center gap-1.5 text-xs font-semibold text-amber-400"><span className="w-2 h-2 rounded-full bg-amber-400"></span> Calculating...</span>;
    if (isSearching) return <span className="flex items-center gap-1.5 text-xs font-semibold text-amber-400"><span className="w-2 h-2 rounded-full bg-amber-400"></span> Searching...</span>;
    return <span className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground"><span className="w-2 h-2 rounded-full border border-muted-foreground"></span> No Route</span>;
  };

  return (
    <RequireGroup>
      {(group) => (
        <div className="min-h-screen flex flex-col bg-background pb-8">
          <Topbar group={group} />
      
          <div className="flex-1 max-w-6xl w-full mx-auto p-4 md:p-6 lg:p-8 flex flex-col gap-6">
            
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-semibold text-foreground">Route</h1>
                <p className="text-sm text-muted-foreground mt-1">Plan your RALLY journey</p>
              </div>
              <div className="px-3 py-1.5 rounded-full bg-card border border-border">
                {renderStatus()}
              </div>
            </div>

            <div className="grid lg:grid-cols-[1fr_360px] gap-6 flex-1 items-start">
              
              {/* Map Column */}
              <div className="h-[50vh] lg:h-[70vh] min-h-[400px] w-full rounded-2xl overflow-hidden border border-border bg-card">
                <LiveMap 
                  customDestination={destination ? { lat: destination.latitude, lng: destination.longitude, name: destination.name } : undefined}
                  routeAlternatives={routeAlternatives.map(r => ({
                    id: r.id,
                    coordinates: r.coordinates,
                    selected: r.id === selectedRouteId
                  }))}
                  onRouteSelect={(id) => setSelectedRouteId(id)}
                />
              </div>

              {/* Controls Column */}
              <div className="flex flex-col gap-6 max-h-[70vh] lg:overflow-y-auto no-scrollbar">
                
                {locError && !deviceLoc && (
                  <div className="p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 shrink-0" />
                    <div className="text-sm">
                      <p className="font-semibold mb-1">Current location unavailable.</p>
                      <p className="opacity-90">Enable location access to plan a route from your current position.</p>
                    </div>
                  </div>
                )}

                {routeError && (
                  <div className="p-4 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 shrink-0" />
                    <div className="text-sm">
                      <p className="font-semibold mb-1">Route unavailable</p>
                      <p className="opacity-90">{routeError}</p>
                    </div>
                  </div>
                )}

                {!isCalculating && routeAlternatives.length === 0 ? (
                    <div className={`space-y-4 ${suggestions.length > 0 && !destination ? 'pb-48' : 'pb-4'}`}>
                    <h2 className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Where are you going?</h2>
                    
                    <div className="relative">
                      <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                        <Search className="w-4 h-4 text-muted-foreground" />
                      </div>
                      <input 
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter' && suggestions.length > 0) {
                            handleSelectDestination(suggestions[0]);
                          }
                        }}
                        placeholder="Search destination"
                        disabled={!!destination}
                        className="w-full bg-card border border-border rounded-xl pl-11 pr-4 py-3.5 text-sm text-foreground focus:outline-none focus:border-rally-blue transition-colors disabled:opacity-60"
                      />
                      
                      {suggestions.length > 0 && !destination && (
                        <div className="absolute top-full mt-2 left-0 right-0 z-50 bg-card border border-border rounded-xl shadow-2xl overflow-hidden max-h-60 overflow-y-auto">
                          {suggestions.map((s, i) => (
                            <button 
                              key={i}
                              onClick={() => handleSelectDestination(s)}
                              className="w-full text-left px-4 py-3 text-sm hover:bg-white/5 border-b border-border/50 last:border-0 flex items-start gap-3"
                            >
                              <MapIcon className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                              <span className="truncate">{s.name}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {destination && (
                      <div className="flex gap-3">
                        <button 
                          onClick={handlePlanRoute}
                          disabled={isCalculating || !deviceLoc}
                          className="flex-1 py-3.5 rounded-xl bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                          {isCalculating ? <><Loader2 className="w-4 h-4 animate-spin" /> Calculating...</> : 'Plan Route'}
                        </button>
                        <button 
                          onClick={handleChangeDestination}
                          className="px-4 rounded-xl border border-border hover:bg-white/5 transition-colors flex items-center justify-center"
                          title="Change Destination"
                        >
                          <Edit2 className="w-4 h-4 text-muted-foreground" />
                        </button>
                      </div>
                    )}
                  </div>
                ) : null}

                {isCalculating && (
                  <div className="p-6 rounded-xl border border-border bg-card flex flex-col items-center justify-center text-center gap-4">
                    <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
                    <p className="text-sm font-semibold text-foreground">Finding the best routes...</p>
                  </div>
                )}

                {routeAlternatives.length > 0 && (
                  <div className="space-y-4">
                    <h2 className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Route Options</h2>
                    
                    <div className="space-y-3">
                      {routeAlternatives.map(route => {
                        const isSelected = selectedRouteId === route.id;
                        return (
                          <button
                            key={route.id}
                            onClick={() => setSelectedRouteId(route.id)}
                            className={`w-full text-left p-5 rounded-2xl border transition-colors relative flex flex-col gap-3 ${
                              isSelected
                                ? 'bg-rally-blue/10 border-rally-blue'
                                : 'bg-card border-border hover:border-border/80'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              {route.isRecommended ? (
                                <span className={`text-[10px] font-bold tracking-wider uppercase flex items-center gap-1.5 ${isSelected ? 'text-emerald-400' : 'text-emerald-500/80'}`}>
                                  🟢 Recommended
                                </span>
                              ) : (
                                <span className="text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
                                  Alternative
                                </span>
                              )}
                              
                              {isSelected ? (
                                <span className="flex items-center gap-1 text-xs font-semibold text-rally-blue">
                                  <Check className="w-3.5 h-3.5" /> Selected
                                </span>
                              ) : (
                                <span className="px-3 py-1 rounded-lg bg-white/5 border border-white/10 text-xs font-semibold text-muted-foreground">
                                  Select
                                </span>
                              )}
                            </div>

                            <div className="flex items-end justify-between gap-4">
                              <div>
                                <p className={`text-lg font-bold ${isSelected ? 'text-foreground' : 'text-foreground/80'}`}>
                                  {formatDistance(route.distance)}
                                </p>
                                <p className={`text-xs font-medium mt-0.5 ${isSelected ? 'text-foreground/90' : 'text-muted-foreground'}`}>
                                  {route.isRecommended ? 'Fastest' : 'Alternative route'}
                                </p>
                              </div>
                              <p className={`text-xl font-bold ${isSelected ? 'text-rally-blue' : 'text-foreground'}`}>
                                {formatDuration(route.duration)}
                              </p>
                            </div>
                          </button>
                        );
                      })}
                    </div>

                    <div className="flex gap-3 pt-2">
                      <button 
                        onClick={handleChangeDestination}
                        className="px-4 py-3.5 rounded-xl border border-border text-foreground text-sm font-semibold hover:bg-white/5 transition-colors"
                        title="Change Destination"
                      >
                        Change
                      </button>
                      <button 
                        onClick={handleStartTrip}
                        disabled={!selectedRouteId}
                        className="flex-1 py-3.5 rounded-xl bg-rally-blue text-background text-sm font-bold hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        Start Trip <ArrowRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
                
              </div>
            </div>

          </div>
        </div>
      )}
    </RequireGroup>
  );
}
