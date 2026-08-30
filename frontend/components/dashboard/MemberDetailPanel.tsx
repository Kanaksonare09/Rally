'use client';

import Link from 'next/link';
import { X, Compass, Gauge, Navigation2, Clock, MapPin, ShieldCheck } from 'lucide-react';
import type { Member } from '@/lib/mock/types';
import { STATUS_STYLE } from './status';

export default function MemberDetailPanel({ member, onClose }: { member: Member; onClose: () => void }) {
  const style = STATUS_STYLE[member.status];

  const rows = [
    { icon: MapPin, label: 'Current location', value: `${member.lat.toFixed(4)}, ${member.lng.toFixed(4)}` },
    { icon: Gauge, label: 'Speed', value: `${member.speedKmh} km/h` },
    { icon: Navigation2, label: 'Heading', value: `${member.headingDeg}°` },
    { icon: Compass, label: 'Distance from group', value: member.distanceFromGroupM === 0 ? 'At group center' : `${member.distanceFromGroupM}m` },
    { icon: Clock, label: 'Last seen', value: member.lastSeen },
    { icon: ShieldCheck, label: 'Safety state', value: style.label },
  ];

  return (
    <div className="fixed inset-0 z-[2000] flex justify-end">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full sm:max-w-sm h-full bg-card border-l border-border p-6 overflow-y-auto">
        <button onClick={onClose} aria-label="Close" className="absolute top-5 right-5 text-muted-foreground hover:text-foreground">
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="w-14 h-14 rounded-full bg-rally-blue/15 border border-rally-blue/30 text-rally-blue font-bold flex items-center justify-center text-lg">
            {member.name.charAt(0)}
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">{member.name}</h2>
            {member.role === 'Leader' && (
              <p className="text-xs font-medium text-rally-blue mt-0.5">Rally Creator / Leader</p>
            )}
          </div>
        </div>

        <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border mb-6 ${style.bg} ${style.border} ${style.text}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          {style.label}
        </span>

        <div className="space-y-4">
          {rows.map((row) => {
            const Icon = row.icon;
            return (
              <div key={row.label} className="flex items-center justify-between text-sm border-b border-border pb-3">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Icon className="w-4 h-4" /> {row.label}
                </span>
                <span className="text-foreground font-medium">{row.value}</span>
              </div>
            );
          })}
        </div>

        <Link
          href="/dashboard"
          className="mt-6 block text-center w-full py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
        >
          View on map
        </Link>
      </div>
    </div>
  );
}
