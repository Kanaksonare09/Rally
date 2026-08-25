'use client';

import { Route, Clock, Users, BellRing } from 'lucide-react';
import type { TripStats as TripStatsType } from '@/lib/mock/types';

export default function TripStats({ trip }: { trip: TripStatsType }) {
  const hours = Math.floor(trip.durationMin / 60);
  const mins = trip.durationMin % 60;

  const items = [
    { label: 'Distance', value: `${trip.distanceKm} km`, icon: Route },
    { label: 'Duration', value: `${hours}h ${mins}m`, icon: Clock },
    { label: 'Members', value: `${trip.membersCount}`, icon: Users },
    { label: 'Alerts', value: `${trip.alertsCount}`, icon: BellRing },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.label} className="rounded-2xl border border-border bg-card p-4">
            <Icon className="w-4 h-4 text-muted-foreground mb-2" />
            <p className="text-lg font-bold text-foreground leading-none">{item.value}</p>
            <p className="text-[11px] text-muted-foreground mt-1.5">{item.label}</p>
          </div>
        );
      })}
    </div>
  );
}
