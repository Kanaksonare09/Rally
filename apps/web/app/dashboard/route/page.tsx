'use client';

import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import LiveMap from '@/components/map/LiveMap';

export default function RoutePage() {
  return (
    <RequireGroup>
      {(group) => (
        <div className="min-h-screen flex flex-col">
          <Topbar group={group} />
          <div className="flex-1 p-4 md:p-6">
            <h1 className="text-xl font-semibold text-foreground mb-5">Route</h1>
            <div className="h-[70vh] min-h-[420px]">
              <LiveMap group={group} />
            </div>
          </div>
        </div>
      )}
    </RequireGroup>
  );
}
