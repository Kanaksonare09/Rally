'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { User, Bell, MapPin, ShieldHalf, Palette, KeyRound, LogOut } from 'lucide-react';
import Topbar from '@/components/dashboard/Topbar';
import Toggle from '@/components/dashboard/Toggle';
import { SettingsSection, SettingsRow } from '@/components/dashboard/SettingsSection';
import RequireAuth from '@/components/dashboard/RequireAuth';
import { useGroup } from '@/lib/group/useGroup';
import { useSettings } from '@/lib/mock/useSettings';
import { groupService } from '@/lib/group/groupService';
import { useAuth } from '@/lib/auth/AuthProvider';
import DemoModePanel from '@/components/dashboard/DemoModePanel';

const selectClass =
  'bg-card border border-border rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none focus:border-rally-blue transition-colors';

export default function SettingsPage() {
  return (
    <RequireAuth>
      <SettingsContent />
    </RequireAuth>
  );
}

function SettingsContent() {
  const router = useRouter();
  const { group } = useGroup();
  const { user, signOut } = useAuth();
  const { settings, update } = useSettings();
  const [loggingOut, setLoggingOut] = useState(false);

  // Never a fabricated identity — seed the profile display from the
  // real authenticated Supabase user the first time settings load with
  // nothing saved locally yet (Phase 13, item 44/51).
  useEffect(() => {
    if (!user) return;
    if (!settings.profile.email && !settings.profile.name) {
      update({
        profile: {
          name: (user.user_metadata?.full_name as string | undefined) ?? user.email?.split('@')[0] ?? 'You',
          email: user.email ?? '',
        },
      });
    }
    // Only re-run if the user identity itself changes, not on every settings update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const handleLogout = async () => {
    setLoggingOut(true);
    groupService.leaveGroup();
    await signOut();
    router.push('/');
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 max-w-2xl space-y-5">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage your profile, alerts, and safety preferences.</p>
        </div>

        <SettingsSection title="Profile" icon={User}>
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-rally-blue/15 border border-rally-blue/30 text-rally-blue font-bold flex items-center justify-center text-lg shrink-0">
              {(settings.profile.name || 'Y').charAt(0).toUpperCase()}
            </div>
            <button
              type="button"
              disabled
              title="Not available yet"
              className="text-sm font-semibold text-muted-foreground cursor-not-allowed"
            >
              Change avatar
            </button>
          </div>
          <SettingsRow label="Name" description="Stored on this device only — not synced across devices yet">
            <input
              value={settings.profile.name}
              onChange={(e) => update({ profile: { ...settings.profile, name: e.target.value } })}
              className="bg-card border border-border rounded-lg px-3 py-1.5 text-sm text-foreground text-right focus:outline-none focus:border-rally-blue transition-colors w-40"
            />
          </SettingsRow>
          <SettingsRow label="Email" description="From your account — sign-in email can't be changed here">
            <input
              value={settings.profile.email}
              readOnly
              className="bg-card border border-border rounded-lg px-3 py-1.5 text-sm text-muted-foreground text-right w-52 cursor-not-allowed"
            />
          </SettingsRow>
        </SettingsSection>

        <DemoModePanel />

        <SettingsSection title="Notifications" icon={Bell}>
          <SettingsRow label="Alert notifications" description="Route deviations, separation, and stops">
            <Toggle
              checked={settings.notifications.alerts}
              onChange={(v) => update({ notifications: { ...settings.notifications, alerts: v } })}
              label="Alert notifications"
            />
          </SettingsRow>
          <SettingsRow label="SOS notifications" description="Emergency alerts from your group">
            <Toggle
              checked={settings.notifications.sos}
              onChange={(v) => update({ notifications: { ...settings.notifications, sos: v } })}
              label="SOS notifications"
            />
          </SettingsRow>
          <SettingsRow label="Connectivity alerts" description="When a member loses signal">
            <Toggle
              checked={settings.notifications.connectivity}
              onChange={(v) => update({ notifications: { ...settings.notifications, connectivity: v } })}
              label="Connectivity alerts"
            />
          </SettingsRow>
          <SettingsRow label="Trip summaries" description="Recap after every completed trip">
            <Toggle
              checked={settings.notifications.tripSummaries}
              onChange={(v) => update({ notifications: { ...settings.notifications, tripSummaries: v } })}
              label="Trip summaries"
            />
          </SettingsRow>
        </SettingsSection>

        <SettingsSection title="Location" icon={MapPin}>
          <SettingsRow label="Location sharing" description="Share your position with your group">
            <Toggle
              checked={settings.location.sharing}
              onChange={(v) => update({ location: { ...settings.location, sharing: v } })}
              label="Location sharing"
            />
          </SettingsRow>
          <SettingsRow label="Location accuracy">
            <select
              value={settings.location.accuracy}
              onChange={(e) => update({ location: { ...settings.location, accuracy: e.target.value as typeof settings.location.accuracy } })}
              className={selectClass}
            >
              <option value="high">High</option>
              <option value="balanced">Balanced</option>
              <option value="low">Low</option>
            </select>
          </SettingsRow>
          <SettingsRow label="Background tracking">
            <select
              value={settings.location.backgroundTracking}
              onChange={(e) =>
                update({ location: { ...settings.location, backgroundTracking: e.target.value as typeof settings.location.backgroundTracking } })
              }
              className={selectClass}
            >
              <option value="always">Always</option>
              <option value="while_active">While trip is active</option>
              <option value="never">Never</option>
            </select>
          </SettingsRow>
        </SettingsSection>

        <SettingsSection title="Safety" icon={ShieldHalf}>
          <SettingsRow label="Alert sensitivity">
            <select
              value={settings.safety.alertSensitivity}
              onChange={(e) => update({ safety: { ...settings.safety, alertSensitivity: e.target.value as typeof settings.safety.alertSensitivity } })}
              className={selectClass}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </SettingsRow>
          <SettingsRow label="Separation threshold" description={`${settings.safety.separationThresholdM}m from group`}>
            <input
              type="range"
              min={50}
              max={500}
              step={10}
              value={settings.safety.separationThresholdM}
              onChange={(e) => update({ safety: { ...settings.safety, separationThresholdM: Number(e.target.value) } })}
              className="w-32 accent-rally-blue"
            />
          </SettingsRow>
          <SettingsRow label="Route deviation threshold" description={`${settings.safety.routeDeviationThresholdM}m off route`}>
            <input
              type="range"
              min={25}
              max={300}
              step={5}
              value={settings.safety.routeDeviationThresholdM}
              onChange={(e) => update({ safety: { ...settings.safety, routeDeviationThresholdM: Number(e.target.value) } })}
              className="w-32 accent-rally-blue"
            />
          </SettingsRow>
        </SettingsSection>

        <SettingsSection title="Appearance" icon={Palette}>
          <SettingsRow label="Theme">
            <div className="flex items-center gap-1.5">
              {(['dark', 'light', 'system'] as const).map((theme) => (
                <button
                  key={theme}
                  onClick={() => update({ appearance: { theme } })}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border capitalize transition-colors ${
                    settings.appearance.theme === theme
                      ? 'bg-rally-blue/15 border-rally-blue/40 text-rally-blue'
                      : 'bg-card border-border text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {theme}
                </button>
              ))}
            </div>
          </SettingsRow>
        </SettingsSection>

        <SettingsSection title="Account" icon={KeyRound}>
          <SettingsRow label="Password" description="Last changed a while ago">
            <button type="button" className="text-sm font-semibold text-rally-blue hover:underline">
              Change password
            </button>
          </SettingsRow>
          <SettingsRow label="Sign out of RALLY">
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-xs font-semibold hover:bg-red-500/20 transition-colors disabled:opacity-60"
            >
              <LogOut className="w-3.5 h-3.5" /> {loggingOut ? 'Signing out…' : 'Logout'}
            </button>
          </SettingsRow>
        </SettingsSection>
      </div>
    </div>
  );
}
