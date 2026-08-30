'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ShieldCheck, Check, MapPin, X, AlertTriangle, AlertCircle, Info, BellRing, Navigation } from 'lucide-react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import { groupService } from '@/lib/mock/groupService';
import type { AlertItem, Group } from '@/lib/mock/types';

// Helper to get relative time
function timeAgo(dateInput: string | number) {
  const date = new Date(dateInput);
  const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);

  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  return `${days} days ago`;
}

// Severity mapping
const SEVERITY_CONFIG = {
  info: { label: '🟢 INFO', icon: Info, colorClass: 'text-emerald-400', bgClass: 'bg-emerald-400/10' },
  warning: { label: '🟡 WARNING', icon: AlertTriangle, colorClass: 'text-amber-400', bgClass: 'bg-amber-400/10' },
  high: { label: '🟠 HIGH', icon: AlertCircle, colorClass: 'text-orange-500', bgClass: 'bg-orange-500/10' },
  critical: { label: '🔴 CRITICAL', icon: BellRing, colorClass: 'text-red-500', bgClass: 'bg-red-500/10' },
};

function AlertsContent({ group }: { group: Group }) {
  const router = useRouter();
  const [filter, setFilter] = useState<'all' | 'unread' | 'active' | 'resolved'>('all');
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);

  const alerts = group.alerts || [];
  
  const totalCount = alerts.length;
  const unreadCount = alerts.filter(a => !a.isRead).length;
  const activeCount = alerts.filter(a => a.status === 'active').length;

  const filteredAlerts = alerts
    .filter(a => {
      if (filter === 'unread') return !a.isRead;
      if (filter === 'active') return a.status === 'active';
      if (filter === 'resolved') return a.status === 'resolved';
      return true;
    })
    .sort((a, b) => new Date(b.time || b.createdAt || 0).getTime() - new Date(a.time || a.createdAt || 0).getTime());

  const handleMarkAllRead = () => {
    groupService.markAllAlertsAsRead();
  };

  const handleMarkAsRead = (id: string) => {
    groupService.markAlertAsRead(id);
    if (selectedAlert?.id === id) {
      setSelectedAlert({ ...selectedAlert, isRead: true });
    }
  };

  const handleViewOnMap = () => {
    // Navigate to Live Trip
    // In a real app we'd pass a query parameter to center map: e.g. /dashboard/trip?lat=X&lng=Y
    router.push('/dashboard/trip');
  };

  return (
    <div className="min-h-screen flex flex-col bg-background relative">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 lg:p-8 space-y-6 max-w-4xl mx-auto w-full">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Alerts</h1>
            <p className="text-sm text-muted-foreground mt-1">Stay informed about your RALLY</p>
          </div>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-foreground text-sm font-semibold hover:bg-white/10 transition-colors shrink-0"
            >
              Mark all as read
            </button>
          )}
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-border bg-card p-4 text-center sm:text-left sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between">
            <span className="text-[10px] sm:text-xs font-bold text-muted-foreground/80 tracking-wider uppercase mb-1 sm:mb-0">All</span>
            <span className="text-2xl font-bold text-foreground">{totalCount}</span>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center sm:text-left sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between">
            <span className="text-[10px] sm:text-xs font-bold text-muted-foreground/80 tracking-wider uppercase mb-1 sm:mb-0">Unread</span>
            <span className={`text-2xl font-bold ${unreadCount > 0 ? 'text-rally-blue' : 'text-foreground'}`}>{unreadCount}</span>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center sm:text-left sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between">
            <span className="text-[10px] sm:text-xs font-bold text-muted-foreground/80 tracking-wider uppercase mb-1 sm:mb-0">Active</span>
            <span className={`text-2xl font-bold ${activeCount > 0 ? 'text-amber-400' : 'text-foreground'}`}>{activeCount}</span>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 hide-scrollbar">
          {(['all', 'unread', 'active', 'resolved'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-full text-sm font-semibold capitalize shrink-0 transition-colors ${
                filter === f
                  ? 'bg-rally-blue text-white'
                  : 'bg-white/5 text-muted-foreground hover:bg-white/10 hover:text-foreground'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Alert List */}
        <div className="space-y-3">
          <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase px-2">Alerts</p>
          
          {totalCount === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-center border border-border rounded-2xl bg-card">
              <div className="w-16 h-16 rounded-full bg-emerald-400/10 border border-emerald-400/30 flex items-center justify-center text-emerald-400 mb-6">
                <ShieldCheck className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-bold text-foreground mb-2">You're all clear</h2>
              <p className="text-muted-foreground text-sm max-w-xs mx-auto">
                No active alerts for your RALLY. Your group is ready to travel.
              </p>
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="text-center p-8 border border-border rounded-2xl bg-card text-muted-foreground">
              <p className="text-sm font-medium">No alerts match the current filter.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {filteredAlerts.map(alert => {
                const isUnread = !alert.isRead;
                const config = SEVERITY_CONFIG[alert.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.info;
                
                return (
                  <div
                    key={alert.id}
                    className={`relative p-5 rounded-2xl border transition-colors bg-card ${
                      isUnread ? 'border-rally-blue/40 bg-rally-blue/5' : 'border-border hover:border-border/80'
                    }`}
                  >
                    {isUnread && (
                      <span className="absolute top-5 left-3 w-2 h-2 rounded-full bg-rally-blue animate-pulse" />
                    )}
                    <div className={`pl-3`}>
                      <div className="flex items-start justify-between gap-4 mb-2">
                        <div>
                          <p className={`text-xs font-bold ${config.colorClass} tracking-wide`}>
                            {config.label} {alert.status === 'resolved' && '· ✓ RESOLVED'}
                          </p>
                          <h3 className={`text-base font-semibold mt-1 ${isUnread ? 'text-white' : 'text-foreground'}`}>
                            {alert.message}
                          </h3>
                        </div>
                        <button
                          onClick={() => setSelectedAlert(alert)}
                          className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-semibold hover:bg-white/10 transition-colors shrink-0"
                        >
                          View
                        </button>
                      </div>
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {alert.detail}
                      </p>
                      <div className="flex items-center gap-3 mt-4 text-xs font-medium text-muted-foreground">
                        {alert.memberName && (
                          <span className="flex items-center gap-1.5 text-foreground">
                            {alert.memberName}
                          </span>
                        )}
                        {alert.memberName && <span>·</span>}
                        <span>{timeAgo(alert.time || alert.createdAt || Date.now())}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Alert Details Modal */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-card border border-border rounded-2xl w-full max-w-md shadow-xl relative animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
            
            <div className="flex items-center justify-between p-4 border-b border-border">
              <h3 className="text-lg font-bold text-foreground">Alert Details</h3>
              <button
                onClick={() => setSelectedAlert(null)}
                className="p-2 -mr-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-6">
              {(() => {
                const config = SEVERITY_CONFIG[selectedAlert.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.info;
                return (
                  <>
                    <div>
                      <p className={`text-sm font-bold ${config.colorClass} tracking-wide mb-2`}>
                        {config.label}
                      </p>
                      <h4 className="text-xl font-bold text-foreground">{selectedAlert.message}</h4>
                    </div>

                    {selectedAlert.memberName && (
                      <div>
                        <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-1">Member</p>
                        <p className="text-base font-medium text-foreground">{selectedAlert.memberName}</p>
                      </div>
                    )}

                    <div>
                      <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-1">Details</p>
                      <p className="text-sm text-foreground/90 leading-relaxed">{selectedAlert.detail}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-1">Detected</p>
                        <p className="text-sm font-medium text-foreground">{timeAgo(selectedAlert.time || selectedAlert.createdAt || Date.now())}</p>
                      </div>
                      <div>
                        <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-1">Status</p>
                        <p className={`text-sm font-bold ${selectedAlert.status === 'active' ? 'text-amber-400' : 'text-emerald-400'}`}>
                          {selectedAlert.status.toUpperCase()}
                        </p>
                      </div>
                    </div>
                  </>
                );
              })()}
            </div>

            <div className="p-4 border-t border-border flex flex-col gap-2">
              <button
                onClick={handleViewOnMap}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-rally-blue/10 border border-rally-blue/30 text-rally-blue text-sm font-bold hover:bg-rally-blue/20 transition-colors"
              >
                <MapPin className="w-4 h-4" /> View on Map
              </button>
              
              {!selectedAlert.isRead && (
                <button
                  onClick={() => handleMarkAsRead(selectedAlert.id)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-foreground text-sm font-bold hover:bg-white/10 transition-colors"
                >
                  <Check className="w-4 h-4" /> Mark as Read
                </button>
              )}
            </div>

          </div>
        </div>
      )}
    </div>
  );
}

export default function AlertsPage() {
  return (
    <RequireGroup>
      {(group) => <AlertsContent group={group} />}
    </RequireGroup>
  );
}
