'use client';

import 'leaflet/dist/leaflet.css';
import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import type { TripSummary } from '@/lib/mock/types';

const MapContainer = dynamic(() => import('react-leaflet').then((m) => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then((m) => m.TileLayer), { ssr: false });
const Marker = dynamic(() => import('react-leaflet').then((m) => m.Marker), { ssr: false });
const Popup = dynamic(() => import('react-leaflet').then((m) => m.Popup), { ssr: false });
const Polyline = dynamic(() => import('react-leaflet').then((m) => m.Polyline), { ssr: false });
const MapBridge = dynamic(() => import('./MapBridge'), { ssr: false });

export default function RouteReplayMap({ summary }: { summary: TripSummary }) {
  const [mounted, setMounted] = useState(false);
  const [L, setL] = useState<any>(null);

  useEffect(() => {
    setMounted(true);
    import('leaflet').then((mod) => setL(mod.default));
  }, []);

  if (!mounted || !L || summary.route.length === 0) {
    return (
      <div className="w-full h-full min-h-[360px] rounded-2xl border border-border bg-card flex items-center justify-center text-muted-foreground">
        <div className="w-8 h-8 border-2 border-rally-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const dot = (hex: string, size = 16) =>
    L.divIcon({
      className: '',
      html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${hex};border:2px solid white;box-shadow:0 0 10px ${hex}CC;"></div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });

  const destinationIcon = L.divIcon({
    className: '',
    html: `<div style="width:16px;height:16px;border-radius:4px;background:#19BFFF;transform:rotate(45deg);border:2px solid white;box-shadow:0 0 10px rgba(25,191,255,0.8);"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });

  const alertIcon = L.divIcon({
    className: '',
    html: `<div style="width:20px;height:20px;border-radius:6px;background:#F59E0B;border:2px solid #0A0A0A;display:flex;align-items:center;justify-content:center;color:#0A0A0A;font-size:12px;font-weight:900;">!</div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

  const deviationIcon = L.divIcon({
    className: '',
    html: `<div style="width:20px;height:20px;border-radius:50%;background:#F87171;border:2px solid #0A0A0A;box-shadow:0 0 10px rgba(248,113,113,0.8);"></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

  const routePositions = summary.route.map((wp) => [wp.lat, wp.lng]) as [number, number][];
  const start = routePositions[0];

  return (
    <div className="relative w-full h-full min-h-[360px] rounded-2xl overflow-hidden border border-border">
      <MapContainer center={start} zoom={13} zoomControl={false} scrollWheelZoom style={{ width: '100%', height: '100%' }}>
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap contributors'
        />
        <MapBridge
          onReady={(map) => {
            const pts: [number, number][] = [...routePositions, [summary.destinationLat, summary.destinationLng]];
            map.fitBounds(pts, { padding: [50, 50] });
          }}
        />

        <Polyline positions={routePositions} color="#19BFFF" weight={4} opacity={0.8} />

        <Marker position={start} icon={dot('#34D399')}>
          <Popup>Start</Popup>
        </Marker>

        <Marker position={[summary.destinationLat, summary.destinationLng]} icon={destinationIcon}>
          <Popup>{summary.destination}</Popup>
        </Marker>

        {summary.alertPoints.map((p, i) => (
          <Marker key={i} position={[p.lat, p.lng]} icon={alertIcon}>
            <Popup>{p.label}</Popup>
          </Marker>
        ))}

        {summary.deviationPoint && (
          <Marker position={[summary.deviationPoint.lat, summary.deviationPoint.lng]} icon={deviationIcon}>
            <Popup>Route deviation</Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
