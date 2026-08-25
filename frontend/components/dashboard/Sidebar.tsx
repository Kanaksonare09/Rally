'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Navigation,
  Users,
  BellRing,
  Map,
  History,
  Settings,
} from 'lucide-react';
import { useGroup } from '@/lib/mock/useGroup';

const NAV_ITEMS = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Live Trip', href: '/dashboard/trip', icon: Navigation },
  { label: 'Members', href: '/dashboard/members', icon: Users },
  { label: 'Alerts', href: '/dashboard/alerts', icon: BellRing },
  { label: 'Route', href: '/dashboard/route', icon: Map },
  { label: 'Trip History', href: '/dashboard/history', icon: History },
  { label: 'Settings', href: '/dashboard/settings', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { group } = useGroup();
  const me = group?.members.find((m) => m.isCurrentUser);

  return (
    <aside className="hidden md:flex flex-col w-60 shrink-0 h-screen sticky top-0 border-r border-border bg-card">
      <Link href="/" className="flex items-center px-6 h-16 border-b border-border">
        <img src="/assets/rally-wordmark.png" alt="RALLY" className="h-9 w-auto mt-2" />
      </Link>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? 'bg-rally-blue/10 text-rally-blue border border-rally-blue/30'
                  : 'text-muted-foreground hover:text-foreground hover:bg-white/5 border border-transparent'
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 py-4 border-t border-border">
        <div className="flex items-center gap-3 px-3 py-2 rounded-lg">
          <div className="w-9 h-9 rounded-full bg-rally-blue/20 border border-rally-blue/40 text-rally-blue font-bold flex items-center justify-center text-sm">
            {(me?.name ?? 'Y').charAt(0)}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground truncate">{me?.name ?? 'You'}</p>
            <p className="text-xs text-muted-foreground truncate">{me?.role ?? 'Leader'}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
