'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Navigation,
  Users,
  BellRing,
  Map,
  History,
  Settings,
  LogOut,
  ChevronDown,
} from 'lucide-react';
import { useGroup } from '@/lib/mock/useGroup';
import { supabase } from '@/lib/supabase';

const SECTIONS = [
  {
    label: 'MAIN',
    items: [
      { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    ],
  },
  {
    label: 'LIVE',
    items: [
      { label: 'Live Trip', href: '/dashboard/trip', icon: Navigation },
      { label: 'Members', href: '/dashboard/members', icon: Users },
      { label: 'Alerts', href: '/dashboard/alerts', icon: BellRing },
    ],
  },
  {
    label: 'TRIP',
    items: [
      { label: 'Route', href: '/dashboard/route', icon: Map },
      { label: 'Trip History', href: '/dashboard/history', icon: History },
    ],
  },
  {
    label: 'SYSTEM',
    items: [
      { label: 'Settings', href: '/dashboard/settings', icon: Settings },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { group } = useGroup();
  const me = group?.members.find((m) => m.isCurrentUser);
  const [profileOpen, setProfileOpen] = useState(false);
  const [actualName, setActualName] = useState('User');
  const [actualEmail, setActualEmail] = useState('');

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user) {
        setActualEmail(user.email || '');
        setActualName(user.user_metadata?.full_name || user.user_metadata?.name || 'User');
      }
    });
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.push('/login');
  };

  const displayName = me?.name || actualName;

  return (
    <aside className="hidden md:flex flex-col w-60 shrink-0 h-screen sticky top-0 border-r border-border bg-card">
      <Link href="/" className="flex items-center px-5 h-16 border-b border-border">
        <img
          src="/assets/new-rally-logo-transparent.png"
          alt="RALLY"
          className="h-7 w-auto object-contain opacity-90 hover:opacity-100 transition-opacity"
        />
      </Link>

      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] px-3 mb-2">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname === item.href;
                const Icon = item.icon;
                // Disable Live/Trip items when no group exists
                const needsGroup = item.href !== '/dashboard' && item.href !== '/dashboard/settings';
                const disabled = needsGroup && !group;

                return (
                  <Link
                    key={item.href}
                    href={disabled ? '#' : item.href}
                    onClick={(e) => disabled && e.preventDefault()}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      active
                        ? 'bg-rally-blue/10 text-rally-blue border border-rally-blue/30'
                        : disabled
                        ? 'text-muted-foreground/40 cursor-not-allowed border border-transparent'
                        : 'text-muted-foreground hover:text-foreground hover:bg-white/5 border border-transparent'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-3 py-3 border-t border-border relative">
        <button
          onClick={() => setProfileOpen(!profileOpen)}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors"
        >
          <div className="w-9 h-9 rounded-full bg-rally-blue/20 border border-rally-blue/40 text-rally-blue font-bold flex items-center justify-center text-sm uppercase">
            {displayName.charAt(0)}
          </div>
          <div className="min-w-0 flex-1 text-left">
            <p className="text-sm font-semibold text-foreground truncate">{displayName}</p>
            {actualEmail && <p className="text-[11px] text-muted-foreground truncate">{actualEmail}</p>}
          </div>
          <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform ${profileOpen ? 'rotate-180' : ''}`} />
        </button>

        {profileOpen && (
          <div className="absolute bottom-full left-3 right-3 mb-1 bg-card border border-border rounded-xl shadow-2xl shadow-black/60 overflow-hidden z-50">
            <Link
              href="/dashboard/settings"
              onClick={() => setProfileOpen(false)}
              className="flex items-center gap-3 px-4 py-3 text-sm text-foreground hover:bg-white/5 transition-colors"
            >
              <Settings className="w-4 h-4 text-muted-foreground" />
              Settings
            </Link>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-400 hover:bg-red-500/10 transition-colors border-t border-border"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
