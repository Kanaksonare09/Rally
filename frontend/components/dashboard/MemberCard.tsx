'use client';

import { Gauge } from 'lucide-react';
import type { Member } from '@/lib/mock/types';
import { STATUS_STYLE } from './status';

export default function MemberCard({ member, onClick }: { member: Member; onClick: () => void }) {
  const style = STATUS_STYLE[member.status];

  return (
    <button
      onClick={onClick}
      className="w-full text-left rounded-2xl border border-border bg-card p-4 hover:border-rally-blue/40 transition-colors"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative shrink-0">
            <div className="w-11 h-11 rounded-full bg-rally-blue/15 border border-rally-blue/30 text-rally-blue font-bold flex items-center justify-center text-sm">
              {member.name.charAt(0)}
            </div>
            <span
              className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-card ${
                member.online ? 'bg-emerald-400' : 'bg-slate-500'
              }`}
            />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">{member.name}</p>
          </div>
        </div>
        <span className={`text-[11px] font-semibold px-2 py-1 rounded-full border ${style.bg} ${style.border} ${style.text} shrink-0`}>
          {style.label}
        </span>
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground pt-3 border-t border-border">
        {member.online ? (
          <>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Online
            </span>
            <span className="flex items-center gap-1">
              <Gauge className="w-3.5 h-3.5" /> {member.speedKmh} km/h
            </span>
            <span>{member.distanceFromGroupM === 0 ? 'Group center' : `${member.distanceFromGroupM}m behind`}</span>
          </>
        ) : (
          <>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-500" /> Offline
            </span>
            <span>Last seen {member.lastSeen}</span>
            <span>Connectivity issue</span>
          </>
        )}
      </div>
    </button>
  );
}
