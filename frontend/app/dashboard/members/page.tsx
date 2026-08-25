'use client';

import { useState } from 'react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import MemberCard from '@/components/dashboard/MemberCard';
import MemberDetailPanel from '@/components/dashboard/MemberDetailPanel';
import GroupSummary from '@/components/dashboard/GroupSummary';
import type { Member } from '@/lib/mock/types';

export default function MembersPage() {
  const [selected, setSelected] = useState<Member | null>(null);

  return (
    <RequireGroup>
      {(group) => {
        const online = group.members.filter((m) => m.online).length;
        return (
          <div className="min-h-screen flex flex-col">
            <Topbar group={group} />

            <div className="flex-1 p-4 md:p-6 space-y-6">
              <div>
                <h1 className="text-xl font-semibold text-foreground">Members</h1>
                <p className="text-sm text-muted-foreground mt-1">
                  {group.members.length} members · {online} online
                </p>
              </div>

              <GroupSummary members={group.members} />

              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {group.members.map((member) => (
                  <MemberCard key={member.id} member={member} onClick={() => setSelected(member)} />
                ))}
              </div>
            </div>

            {selected && <MemberDetailPanel member={selected} onClose={() => setSelected(null)} />}
          </div>
        );
      }}
    </RequireGroup>
  );
}
