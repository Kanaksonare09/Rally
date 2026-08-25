'use client';

export type AlertFilter =
  | 'all'
  | 'active'
  | 'resolved'
  | 'critical'
  | 'warning'
  | 'connectivity'
  | 'route_deviation'
  | 'separation'
  | 'stop'
  | 'sos';

const FILTERS: { value: AlertFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'critical', label: 'Critical' },
  { value: 'warning', label: 'Warning' },
  { value: 'connectivity', label: 'Connectivity' },
  { value: 'route_deviation', label: 'Route' },
  { value: 'separation', label: 'Separation' },
  { value: 'stop', label: 'Stop' },
  { value: 'sos', label: 'SOS' },
];

export default function AlertFilterBar({
  active,
  onChange,
}: {
  active: AlertFilter;
  onChange: (filter: AlertFilter) => void;
}) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-1 px-1">
      {FILTERS.map((f) => (
        <button
          key={f.value}
          onClick={() => onChange(f.value)}
          className={`shrink-0 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
            active === f.value
              ? 'bg-rally-blue/15 border-rally-blue/40 text-rally-blue'
              : 'bg-card border-border text-muted-foreground hover:text-foreground hover:border-white/20'
          }`}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}
