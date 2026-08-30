'use client';

import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { Play, Pause, RotateCcw, Loader2, AlertCircle } from 'lucide-react';
import { getTripReplay } from '@/lib/api/replay';
import { getTrip } from '@/lib/api/trips';
import { getGroupMembers } from '@/lib/api/groups';
import { friendlyErrorMessage } from '@/lib/api/errors';
import type { TripReplay } from '@/lib/api/types';

const MapContainer = dynamic(() => import('react-leaflet').then((m) => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then((m) => m.TileLayer), { ssr: false });
const Marker = dynamic(() => import('react-leaflet').then((m) => m.Marker), { ssr: false });
const Popup = dynamic(() => import('react-leaflet').then((m) => m.Popup), { ssr: false });
const MapBridge = dynamic(() => import('@/components/map/MapBridge'), { ssr: false });

const SPEEDS = [0.5, 1, 2, 4] as const;
const BASE_TICK_MS = 700; // wall-clock time per frame at 1x — not real trip time (item 29: backend-sampled frames, UI just steps through them)

/**
 * Play/Pause/Restart/Timeline/Speed replay of a completed trip, driven
 * entirely by the backend's sampled `GET /trips/{trip_id}/replay` frames
 * — never raw per-second GPS history (Phase 13, item 29).
 */
export default function TripReplayPlayer({ tripId }: { tripId: string }) {
  const [replay, setReplay] = useState<TripReplay | null>(null);
  const [memberNames, setMemberNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [mounted, setMounted] = useState(false);
  const [L, setL] = useState<any>(null);

  useEffect(() => {
    setMounted(true);
    import('leaflet').then((mod) => setL(mod.default));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getTripReplay(tripId)
      .then(async (r) => {
        if (cancelled) return;
        setReplay(r);
        try {
          const trip = await getTrip(tripId);
          const members = await getGroupMembers(trip.group_id);
          if (!cancelled) setMemberNames(Object.fromEntries(members.map((m) => [m.user_id, m.name ?? 'Member'])));
        } catch {
          // Names are a display nicety only — replay still works without them.
        }
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
  }, [tripId]);

  const frameCount = replay?.timeline.length ?? 0;

  useEffect(() => {
    if (!playing || frameCount === 0) return;
    const interval = setInterval(() => {
      setFrameIndex((i) => {
        if (i >= frameCount - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, BASE_TICK_MS / speed);
    return () => clearInterval(interval);
  }, [playing, speed, frameCount]);

  const frame = replay?.timeline[frameIndex] ?? null;

  const memberIcon = useMemo(() => {
    if (!L) return null;
    return (hex: string, label: string) =>
      L.divIcon({
        className: '',
        html: `<div style="width:24px;height:24px;border-radius:50%;background:#0A0A0A;border:2px solid ${hex};color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 0 8px ${hex};">${label.charAt(0).toUpperCase()}</div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });
  }, [L]);

  if (loading) {
    return (
      <div className="w-full h-[360px] rounded-2xl border border-border bg-card flex items-center justify-center text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-[200px] rounded-2xl border border-border bg-card flex flex-col items-center justify-center gap-2 text-center px-6">
        <AlertCircle className="w-5 h-5 text-red-400" />
        <p className="text-sm text-muted-foreground">{error}</p>
      </div>
    );
  }

  if (!replay || replay.timeline.length === 0) {
    return (
      <div className="w-full h-[200px] rounded-2xl border border-border bg-card flex items-center justify-center text-sm text-muted-foreground">
        No replay data available for this trip.
      </div>
    );
  }

  const positions = frame?.members.filter((m) => m.latitude != null && m.longitude != null) ?? [];
  const center: [number, number] = positions.length > 0 ? [positions[0].latitude, positions[0].longitude] : [0, 0];

  return (
    <div className="space-y-3">
      <div className="relative w-full h-[360px] rounded-2xl overflow-hidden border border-border">
        {!mounted || !L ? (
          <div className="w-full h-full flex items-center justify-center bg-card text-muted-foreground">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : (
          <MapContainer center={center} zoom={13} zoomControl={false} scrollWheelZoom style={{ width: '100%', height: '100%' }}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              className="map-tiles-dark"
            />
            <MapBridge
              onReady={(map) => {
                if (positions.length > 0) map.setView(center, 14, { animate: false });
              }}
            />
            {positions.map((m) => (
              <Marker key={m.user_id} position={[m.latitude, m.longitude]} icon={memberIcon?.('#19BFFF', memberNames[m.user_id] ?? 'Member')}>
                <Popup>
                  <div className="text-xs font-semibold">{memberNames[m.user_id] ?? 'Member'}</div>
                  {m.movement_state && <div className="text-[11px] text-neutral-500">{m.movement_state}</div>}
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-card p-4 space-y-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setPlaying((p) => !p)}
            className="w-9 h-9 rounded-full bg-foreground text-background flex items-center justify-center hover:opacity-85 transition-opacity shrink-0"
            aria-label={playing ? 'Pause' : 'Play'}
          >
            {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>
          <button
            onClick={() => {
              setFrameIndex(0);
              setPlaying(false);
            }}
            className="w-9 h-9 rounded-full border border-border text-foreground flex items-center justify-center hover:bg-white/5 transition-colors shrink-0"
            aria-label="Restart"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <input
            type="range"
            min={0}
            max={frameCount - 1}
            value={frameIndex}
            onChange={(e) => {
              setPlaying(false);
              setFrameIndex(Number(e.target.value));
            }}
            className="flex-1 accent-rally-blue"
          />

          <div className="flex items-center gap-1 shrink-0">
            {SPEEDS.map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-2 py-1 rounded-md text-[11px] font-semibold border transition-colors ${
                  speed === s ? 'bg-rally-blue/15 border-rally-blue/40 text-rally-blue' : 'border-border text-muted-foreground hover:text-foreground'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground font-mono">
          {frame ? new Date(frame.timestamp).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' }) : '—'}
          {' · '}Frame {frameIndex + 1} / {frameCount}
        </p>
      </div>
    </div>
  );
}
