'use client';

import { useEffect, useState } from 'react';
import { WifiOff } from 'lucide-react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import GroupHealthCard from '@/components/dashboard/GroupHealthCard';
import AlertPanel from '@/components/dashboard/AlertPanel';
import TripStats from '@/components/dashboard/TripStats';
import SosButton from '@/components/dashboard/SosButton';
import LiveMap from '@/components/map/LiveMap';

export default function DashboardPage() {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    setOnline(navigator.onLine);
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  return (
    <RequireGroup>
      {(group) => (
        <div className="min-h-screen flex flex-col">
          <Topbar group={group} online={online} />

          {!online && (
            <div className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border-b border-red-500/20 text-red-400 text-xs font-medium">
              <WifiOff className="w-3.5 h-3.5" />
              You're offline. Showing the last known positions until connection returns.
            </div>
          )}

          <div className="flex-1 p-4 md:p-6 space-y-5">
            <div className="relative h-[60vh] min-h-[420px] md:h-[calc(100vh-11rem)]">
              <LiveMap group={group} />
              <div className="absolute top-4 left-4 z-[999]">
                <GroupHealthCard group={group} />
              </div>
            </div>

            <TripStats trip={group.trip} />

            <AlertPanel alerts={group.alerts} />
          </div>

          <SosButton />
        </div>
      )}
    </RequireGroup>
  );
}
