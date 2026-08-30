'use client';

import { useState } from 'react';
import { Users, MapPin, Copy, Check, Play } from 'lucide-react';
import type { Group } from '@/lib/mock/types';

export default function RallyOverview({ group, onStartTrip }: { group: Group; onStartTrip?: () => void }) {
  const [copied, setCopied] = useState(false);
  const memberCount = group.members.length;

  const handleCopy = () => {
    navigator.clipboard.writeText(group.joinCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-5 space-y-4 flex flex-col justify-between h-full">
      <div>
        <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] mb-2">RALLY</p>
        <h2 className="text-lg font-semibold text-foreground">{group.name}</h2>
      </div>

      <div className="space-y-2.5">
        <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
          <Users className="w-4 h-4 shrink-0" />
          <span>{memberCount} {memberCount === 1 ? 'member' : 'members'}</span>
        </div>
        {group.destination && group.destination !== 'Destination' && (
          <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
            <MapPin className="w-4 h-4 shrink-0" />
            <span>{group.destination}</span>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-background/50 p-3.5 mt-auto">
        <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] mb-2">JOIN CODE</p>
        <div className="flex items-center justify-between gap-3">
          <p className="text-lg font-bold tracking-[0.08em] text-rally-blue font-mono">{group.joinCode}</p>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-foreground hover:bg-white/5 transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>

      {onStartTrip && (
        <button
          onClick={onStartTrip}
          className="w-full mt-2 py-2.5 rounded-xl bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity flex items-center justify-center gap-2"
        >
          <Play className="w-4 h-4" /> Start Trip
        </button>
      )}
    </div>
  );
}
