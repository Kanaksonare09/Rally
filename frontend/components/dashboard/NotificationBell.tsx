'use client';

import { useEffect, useRef, useState } from 'react';
import { Bell, Loader2, CheckCheck, AlertCircle } from 'lucide-react';
import { listNotifications, markAllNotificationsRead, markNotificationRead } from '@/lib/api/notifications';
import { friendlyErrorMessage } from '@/lib/api/errors';
import { formatRelativeTime } from '@/lib/format';
import type { ApiNotification } from '@/lib/api/types';

/**
 * Notifications are per-user, not per-trip (Phase 13, item 27) — the
 * badge count is fed from the trip dashboard's cached `notifications`
 * section (see Topbar) so opening this never issues an extra request;
 * the dropdown's actual list is only fetched on demand, when opened.
 */
export default function NotificationBell({ unreadCount }: { unreadCount: number }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ApiNotification[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listNotifications({ limit: 20 });
      setItems(response.items);
    } catch (err) {
      setError(friendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = () => {
    const next = !open;
    setOpen(next);
    if (next && items === null) void load();
  };

  const handleMarkRead = async (id: string) => {
    try {
      await markNotificationRead(id);
      setItems((prev) => prev?.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)) ?? prev);
    } catch (err) {
      setError(friendlyErrorMessage(err));
    }
  };

  const handleMarkAll = async () => {
    setMarkingAll(true);
    try {
      await markAllNotificationsRead();
      setItems((prev) => prev?.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })) ?? prev);
    } catch (err) {
      setError(friendlyErrorMessage(err));
    } finally {
      setMarkingAll(false);
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={handleToggle}
        aria-label="Notifications"
        className="relative w-8 h-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-[420px] flex flex-col rounded-xl border border-border bg-card shadow-2xl z-[2100] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <p className="text-sm font-semibold text-foreground">Notifications</p>
            <button
              onClick={handleMarkAll}
              disabled={markingAll || !items?.some((n) => !n.read_at)}
              className="flex items-center gap-1.5 text-xs font-medium text-rally-blue hover:underline disabled:opacity-40 disabled:no-underline"
            >
              <CheckCheck className="w-3.5 h-3.5" /> Mark all read
            </button>
          </div>

          <div className="overflow-y-auto flex-1">
            {loading ? (
              <div className="flex items-center justify-center py-10 text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin" />
              </div>
            ) : error ? (
              <p className="flex items-center gap-2 text-xs text-red-400 px-4 py-6">
                <AlertCircle className="w-4 h-4 shrink-0" /> {error}
              </p>
            ) : !items || items.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-10">No notifications yet.</p>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => !n.read_at && handleMarkRead(n.id)}
                  className={`w-full text-left px-4 py-3 border-b border-border last:border-b-0 hover:bg-white/5 transition-colors ${
                    !n.read_at ? 'bg-rally-blue/5' : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.read_at && <span className="w-1.5 h-1.5 rounded-full bg-rally-blue mt-1.5 shrink-0" />}
                    <div className="min-w-0">
                      <p className="text-sm text-foreground font-medium truncate">{n.title}</p>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.message}</p>
                      <p className="text-[10px] text-muted-foreground/70 mt-1">{formatRelativeTime(n.created_at)}</p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
