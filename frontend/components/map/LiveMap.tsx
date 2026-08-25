'use client';

import 'leaflet/dist/leaflet.css';
import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { LocateFixed, Plus, Minus, Maximize, Route as RouteIcon } from 'lucide-react';
import type { Map as LeafletMap } from 'leaflet';
import type { AlertItem, Group } from '@/lib/mock/types';
import { STATUS_STYLE } from '@/components/dashboard/status';

const MapContainer = dynamic(() => import('react-leaflet').then((m) => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then((m) => m.TileLayer), { ssr: false });
const Marker = dynamic(() => import('react-leaflet').then((m) => m.Marker), { ssr: false });
const Popup = dynamic(() => import('react-leaflet').then((m) => m.Popup), { ssr: false });
const Polyline = dynamic(() => import('react-leaflet').then((m) => m.Polyline), { ssr: false });
const MapBridge = dynamic(() => import('./MapBridge'), { ssr: false });

export default function LiveMap({
  group,
  showStart = false,
  alerts,
}: {
  group: Group;
  showStart?: boolean;
  alerts?: AlertItem[];
}) {
  const [mounted, setMounted] = useState(false);
  const [L, setL] = useState<any>(null);
  const [showRoute, setShowRoute] = useState(true);
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    setMounted(true);
    import('leaflet').then((mod) => setL(mod.default));
  }, []);

  if (!mounted || !L) {
    return (
      <div className="w-full h-full min-h-[420px] rounded-2xl border border-border bg-card flex flex-col items-center justify-center text-muted-foreground gap-3">
        <div className="w-8 h-8 border-2 border-rally-blue border-t-transparent rounded-full animate-spin" />
        <p className="text-sm font-medium">Initializing live map…</p>
      </div>
    );
  }

  const memberIcon = (name: string, hex: string, isMe: boolean) =>
    L.divIcon({
      className: '',
      html: `
        <div style="position:relative;width:36px;height:36px;display:flex;align-items:center;justify-content:center;">
          <div style="position:absolute;width:100%;height:100%;border-radius:50%;background:${hex};opacity:0.3;animation:ping 2s cubic-bezier(0,0,0.2,1) infinite;"></div>
          <div style="width:28px;height:28px;border-radius:50%;background:#0A0A0A;border:2px solid ${hex};color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px ${hex};">
            ${name.charAt(0)}
          </div>
          ${isMe ? `<div style="position:absolute;bottom:-14px;left:50%;transform:translateX(-50%);font-size:9px;font-weight:700;color:${hex};letter-spacing:0.05em;">YOU</div>` : ''}
        </div>
      `,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

  const destinationIcon = L.divIcon({
    className: '',
    html: `
      <div style="position:relative;width:34px;height:34px;display:flex;align-items:center;justify-content:center;">
        <div style="width:16px;height:16px;border-radius:4px;background:#19BFFF;transform:rotate(45deg);box-shadow:0 0 14px rgba(25,191,255,0.8);border:2px solid white;"></div>
      </div>
    `,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });

  const startIcon = L.divIcon({
    className: '',
    html: `
      <div style="position:relative;width:28px;height:28px;display:flex;align-items:center;justify-content:center;">
        <div style="width:16px;height:16px;border-radius:50%;background:#34D399;border:2px solid white;box-shadow:0 0 10px rgba(52,211,153,0.8);"></div>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });

  const alertIcon = L.divIcon({
    className: '',
    html: `
      <div style="width:22px;height:22px;border-radius:6px;background:#F59E0B;border:2px solid #0A0A0A;display:flex;align-items:center;justify-content:center;color:#0A0A0A;font-size:13px;font-weight:900;box-shadow:0 0 8px rgba(245,158,11,0.7);">!</div>
    `,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });

  const routePositions = group.route.map((wp) => [wp.lat, wp.lng]) as [number, number][];
  const groupCenterLat = group.members.reduce((sum, m) => sum + m.lat, 0) / group.members.length;
  const groupCenterLng = group.members.reduce((sum, m) => sum + m.lng, 0) / group.members.length;
  const center: [number, number] = [groupCenterLat, groupCenterLng];

  const handleFitGroup = () => {
    if (!mapRef.current) return;
    const pts = group.members.map((m) => [m.lat, m.lng] as [number, number]);
    pts.push([group.destinationLat, group.destinationLng]);
    mapRef.current.fitBounds(pts, { padding: [60, 60] });
  };

  const handleMapReady = (map: LeafletMap) => {
    mapRef.current = map;
    const pts = group.members.map((m) => [m.lat, m.lng] as [number, number]);
    pts.push([group.destinationLat, group.destinationLng]);
    // animate: false — an animated transition kicked off the instant the
    // map mounts can outlive a React 18 StrictMode dev double-mount
    // (mount -> cleanup -> mount), leaving a transitionend callback that
    // fires against an already-torn-down map instance ("Cannot read
    // properties of undefined (reading '_leaflet_pos')"). User-triggered
    // fit/locate below stay animated since there's no such race there.
    map.fitBounds(pts, { padding: [70, 70], maxZoom: 16, animate: false });
  };

  const handleLocateMe = () => {
    if (!mapRef.current) return;
    const me = group.members.find((m) => m.isCurrentUser);
    if (me) mapRef.current.flyTo([me.lat, me.lng], 15, { duration: 0.6 });
  };

  return (
    <div className="relative w-full h-full min-h-[420px] rounded-2xl overflow-hidden border border-border">
      <MapContainer center={center} zoom={12} zoomControl={false} scrollWheelZoom style={{ width: '100%', height: '100%' }}>
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap contributors'
        />
        <MapBridge onReady={handleMapReady} />

        {showRoute && routePositions.length > 0 && (
          <Polyline positions={routePositions} color="#19BFFF" weight={4} opacity={0.75} dashArray="8, 8" />
        )}

        <Marker position={[group.destinationLat, group.destinationLng]} icon={destinationIcon}>
          <Popup>
            <div className="text-xs font-semibold">{group.destination}</div>
            <div className="text-[11px] text-neutral-500">Destination</div>
          </Popup>
        </Marker>

        {showStart && group.route.length > 0 && (
          <Marker position={[group.route[0].lat, group.route[0].lng]} icon={startIcon}>
            <Popup>
              <div className="text-xs font-semibold">Start</div>
            </Popup>
          </Marker>
        )}

        {alerts?.map((a) => {
          const m = group.members.find((mem) => mem.id === a.memberId);
          if (!m) return null;
          return (
            <Marker key={a.id} position={[m.lat + 0.0008, m.lng + 0.0008]} icon={alertIcon}>
              <Popup>
                <div className="text-xs font-semibold">{a.message}</div>
                <div className="text-[11px] text-neutral-500">{a.detail}</div>
              </Popup>
            </Marker>
          );
        })}

        {group.members.map((m) => {
          const style = STATUS_STYLE[m.status];
          return (
            <Marker key={m.id} position={[m.lat, m.lng]} icon={memberIcon(m.name, style.hex, m.isCurrentUser)}>
              <Popup>
                <div className="space-y-0.5">
                  <div className="text-xs font-bold flex items-center gap-1.5">
                    {m.name} {m.isCurrentUser && <span className="text-[10px] text-neutral-500">(You)</span>}
                  </div>
                  <div className="text-[11px] text-neutral-500">{style.label} · {m.speedKmh} km/h</div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>

      {/* Floating map controls */}
      <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-2">
        <MapControlButton onClick={handleLocateMe} label="Locate me">
          <LocateFixed className="w-4 h-4" />
        </MapControlButton>
        <div className="flex flex-col rounded-xl overflow-hidden border border-white/10 bg-[#0A0A0A]/90 backdrop-blur">
          <button
            onClick={() => mapRef.current?.zoomIn()}
            aria-label="Zoom in"
            className="w-9 h-9 flex items-center justify-center text-white hover:bg-white/10 transition-colors"
          >
            <Plus className="w-4 h-4" />
          </button>
          <div className="h-px bg-white/10" />
          <button
            onClick={() => mapRef.current?.zoomOut()}
            aria-label="Zoom out"
            className="w-9 h-9 flex items-center justify-center text-white hover:bg-white/10 transition-colors"
          >
            <Minus className="w-4 h-4" />
          </button>
        </div>
        <MapControlButton onClick={handleFitGroup} label="Fit group">
          <Maximize className="w-4 h-4" />
        </MapControlButton>
        <MapControlButton onClick={() => setShowRoute((v) => !v)} label="Toggle route" active={showRoute}>
          <RouteIcon className="w-4 h-4" />
        </MapControlButton>
      </div>
    </div>
  );
}

function MapControlButton({
  onClick,
  label,
  children,
  active,
}: {
  onClick: () => void;
  label: string;
  children: React.ReactNode;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`w-9 h-9 rounded-xl flex items-center justify-center border backdrop-blur transition-colors ${
        active
          ? 'bg-rally-blue/20 border-rally-blue/50 text-rally-blue'
          : 'bg-[#0A0A0A]/90 border-white/10 text-white hover:bg-white/10'
      }`}
    >
      {children}
    </button>
  );
}
