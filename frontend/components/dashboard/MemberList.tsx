'use client';

import type { Member } from '@/lib/mock/types';

export default function MemberList({ members }: { members: Member[] }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 space-y-3">
      <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em]">MEMBERS</p>

      <div className="space-y-2">
        {members.map((m) => (
          <div key={m.id} className="flex items-center gap-3 py-1.5">
            <div className="relative">
              <div className="w-8 h-8 rounded-full bg-rally-blue/20 border border-rally-blue/40 text-rally-blue font-bold flex items-center justify-center text-xs">
                {m.name.charAt(0)}
              </div>
              <span
                className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-card ${
                  m.online ? 'bg-emerald-400' : 'bg-muted-foreground'
                }`}
              />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground truncate">
                {m.name}
                {m.isCurrentUser && <span className="text-muted-foreground text-xs ml-1.5">(You)</span>}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
