'use client';

import { useEffect, useState } from 'react';
import { WifiOff } from 'lucide-react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import GroupHealthCard from '@/components/dashboard/GroupHealthCard';
import ActivityFeed from '@/components/dashboard/ActivityFeed';
import SosButton from '@/components/dashboard/SosButton';
import LiveMap from '@/components/map/LiveMap';
import MapTelemetryBar from '@/components/dashboard/MapTelemetryBar';
import NeedsAttentionPanel from '@/components/dashboard/NeedsAttentionPanel';
import MembersSnapshotPanel from '@/components/dashboard/MembersSnapshotPanel';
import TripOverviewPanel from '@/components/dashboard/TripOverviewPanel';

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
      {(group) => {
        const onlineCount = group.members.filter((m) => m.online).length;

        return (
          <div className="min-h-screen flex flex-col bg-[#050505] text-white">
            {/* Topbar Header */}
            <Topbar group={group} online={online} />

            {/* Offline Alert Bar */}
            {!online && (
              <div className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border-b border-red-500/20 text-red-400 text-xs font-medium font-mono">
                <WifiOff className="w-3.5 h-3.5" />
                Offline mode active. Displaying last known telemetry positions.
              </div>
            )}

            {/* Command Center Main Operational Grid */}
            <div className="flex-1 p-4 md:p-6 space-y-6 max-w-7xl mx-auto w-full">
              
              {/* HERO MAP SECTION (Visual Anchor) */}
              <div className="relative rounded-2xl overflow-hidden border border-white/10 shadow-2xl h-[58vh] min-h-[440px]">
                <LiveMap group={group} alerts={group.alerts} />

                {/* Floating Top-Left: Group Health Overlay */}
                <div className="absolute top-4 left-4 z-[999] max-w-[280px]">
                  <GroupHealthCard group={group} />
                </div>

                {/* Floating Bottom: Map Telemetry Strip */}
                <div className="absolute bottom-4 left-4 right-4 z-[999]">
                  <MapTelemetryBar
                    trip={group.trip}
                    onlineCount={onlineCount}
                    totalMembers={group.members.length}
                  />
                </div>
              </div>

              {/* OPERATIONAL SECTION 1: Needs Attention & Live Activity */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
                {/* Needs Attention Panel */}
                <NeedsAttentionPanel alerts={group.alerts} />

                {/* Live Activity Stream */}
                <ActivityFeed members={group.members} />
              </div>

              {/* OPERATIONAL SECTION 2: Members Snapshot & Trip Overview */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
                {/* Group Members Snapshot */}
                <MembersSnapshotPanel members={group.members} />

                {/* Trip Overview & Quick Actions */}
                <TripOverviewPanel group={group} />
              </div>

            </div>

            {/* Emergency SOS Button */}
            <SosButton />
          </div>
        );
      }}
    </RequireGroup>
  );
}
