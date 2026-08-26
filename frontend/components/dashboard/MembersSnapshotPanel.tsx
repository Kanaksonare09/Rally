'use client';

import React from 'react';
import Link from 'next/link';
import { Gauge, ArrowRight } from 'lucide-react';
import type { Member } from '@/lib/mock/types';

export default function MembersSnapshotPanel({ members }: { members: Member[] }) {
  const onlineCount = members.filter((m) => m.online).length;

  return (
    <div className="rounded-xl border border-white/10 bg-[#0A0A0C] p-5 space-y-4 flex flex-col justify-between h-full">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between font-mono">
          <h2 className="text-xs font-bold uppercase tracking-[0.15em] text-white">
            GROUP MEMBERS
          </h2>
          <span className="text-[11px] font-semibold text-white/50 bg-white/5 border border-white/10 px-2 py-0.5 rounded-full">
            {members.length} members · {onlineCount} online
          </span>
        </div>

        {/* Members List */}
        <div className="space-y-2">
          {members.map((member) => (
            <Link
              key={member.id}
              href="/dashboard/members"
              className="flex items-center justify-between p-3 rounded-lg bg-[#0B0C10] border border-white/5 hover:border-white/20 transition-all duration-200 group"
            >
              {/* Left: Avatar & Info */}
              <div className="flex items-center gap-3 min-w-0">
                <div className="relative shrink-0">
                  <div className="w-8 h-8 rounded-full bg-white/10 border border-white/20 text-white font-bold font-mono text-xs flex items-center justify-center">
                    {member.name.charAt(0)}
                  </div>
                  <span
                    className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border border-black ${
                      member.online ? 'bg-emerald-400' : 'bg-neutral-500'
                    }`}
                  />
                </div>

                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-semibold text-white group-hover:text-cyan-300 transition-colors truncate">
                      {member.name}
                    </p>
                    {member.role === 'Leader' && (
                      <span className="px-1.5 py-0.2 text-[9px] font-mono font-bold uppercase bg-white/10 text-white/70 rounded">
                        LEADER
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] font-mono text-white/40 truncate">
                    {member.online ? (
                      member.distanceFromGroupM === 0 ? (
                        'Group center'
                      ) : (
                        <span className="text-amber-400/90">{member.distanceFromGroupM}m behind</span>
                      )
                    ) : (
                      `Offline · ${member.lastSeen}`
                    )}
                  </p>
                </div>
              </div>

              {/* Right: Telemetry/Speed */}
              <div className="font-mono text-xs text-right shrink-0">
                {member.online ? (
                  <div className="flex items-center gap-1 text-white/80">
                    <Gauge className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{member.speedKmh} km/h</span>
                  </div>
                ) : (
                  <span className="text-[10px] text-white/30 uppercase">DISCONNECTED</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Footer Link */}
      <div className="pt-2 border-t border-white/10">
        <Link
          href="/dashboard/members"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
        >
          <span>View all members</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}
