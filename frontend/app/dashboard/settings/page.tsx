'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { X, LogOut, Check } from 'lucide-react';
import Topbar from '@/components/dashboard/Topbar';
import Toggle from '@/components/dashboard/Toggle';
import { useGroup } from '@/lib/mock/useGroup';
import { useSettings } from '@/lib/mock/useSettings';
import { groupService } from '@/lib/mock/groupService';
import { supabase } from '@/lib/supabase';
import { createPortal } from 'react-dom';

export default function SettingsPage() {
  const router = useRouter();
  const { group } = useGroup();
  const { settings, update } = useSettings();

  const [actualName, setActualName] = useState(settings.profile.name);
  const [actualEmail, setActualEmail] = useState(settings.profile.email);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editName, setEditName] = useState('');
  const [editError, setEditError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user) {
        setActualEmail(user.email || '');
        setActualName(user.user_metadata?.full_name || user.user_metadata?.name || 'User');
      }
    });
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    groupService.leaveGroup();
    router.push('/login');
  };

  const handleSaveProfile = async () => {
    const trimmed = editName.trim();
    if (!trimmed) {
      setEditError('Display name cannot be empty.');
      return;
    }
    if (trimmed.length > 50) {
      setEditError('Display name is too long.');
      return;
    }
    setEditError('');
    setIsSaving(true);
    
    const { error } = await supabase.auth.updateUser({
      data: { full_name: trimmed }
    });

    setIsSaving(false);

    if (error) {
      setEditError('Unable to save changes. Please try again.');
    } else {
      setActualName(trimmed);
      update({ profile: { ...settings.profile, name: trimmed } });
      setIsEditModalOpen(false);
      showToast('Profile updated');
    }
  };

  const handleLocationManage = () => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        () => showToast('Location permission granted'),
        () => showToast('Location permission denied or unavailable')
      );
    } else {
      showToast('Geolocation not supported by this browser');
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-background relative pb-8">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 lg:p-8 space-y-8 max-w-2xl mx-auto w-full">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage your account and RALLY preferences</p>
        </div>

        {/* ACCOUNT */}
        <section className="space-y-3">
          <h2 className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Account</h2>
          <div className="rounded-2xl border border-border bg-card p-5">
            <div className="flex items-start sm:items-center justify-between gap-4 flex-col sm:flex-row">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-rally-blue/15 border border-rally-blue/30 text-rally-blue font-bold flex items-center justify-center text-lg shrink-0">
                  {actualName ? actualName.charAt(0).toUpperCase() : 'U'}
                </div>
                <div>
                  <p className="text-base font-bold text-foreground">{actualName}</p>
                  <p className="text-sm text-muted-foreground">{actualEmail}</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setEditName(actualName);
                  setEditError('');
                  setIsEditModalOpen(true);
                }}
                className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-xs font-semibold text-foreground hover:bg-white/10 transition-colors shrink-0 w-full sm:w-auto"
              >
                Edit Profile
              </button>
            </div>
          </div>
        </section>

        {/* PRIVACY & LOCATION */}
        <section className="space-y-3">
          <h2 className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Privacy & Location</h2>
          <div className="rounded-2xl border border-border bg-card divide-y divide-border">
            <div className="p-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-foreground">Location Sharing</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {settings.location.sharing 
                    ? 'Shared with current RALLY members'
                    : 'Location sharing is disabled'}
                </p>
              </div>
              <Toggle
                checked={settings.location.sharing}
                onChange={(v) => {
                  update({ location: { ...settings.location, sharing: v } });
                  showToast(v ? 'Location sharing enabled' : 'Location sharing disabled');
                }}
                label="Location Sharing"
              />
            </div>
            <div className="p-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-foreground">Location Permission</p>
                <p className="text-xs text-muted-foreground mt-1">Manage browser GPS access</p>
              </div>
              <button
                onClick={handleLocationManage}
                className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-xs font-semibold text-foreground hover:bg-white/10 transition-colors shrink-0"
              >
                Manage
              </button>
            </div>
          </div>
        </section>

        {/* NOTIFICATIONS */}
        <section className="space-y-3">
          <h2 className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Notifications</h2>
          <div className="rounded-2xl border border-border bg-card p-5 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-foreground">RALLY Alerts</p>
              <p className="text-xs text-muted-foreground mt-1">Safety and trip notifications</p>
            </div>
            <Toggle
              checked={settings.notifications.alerts}
              onChange={(v) => {
                update({ notifications: { ...settings.notifications, alerts: v } });
                showToast('Preferences saved');
              }}
              label="RALLY Alerts"
            />
          </div>
        </section>

        {/* PREFERENCES */}
        <section className="space-y-3">
          <h2 className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Preferences</h2>
          <div className="rounded-2xl border border-border bg-card divide-y divide-border">
            <div className="p-5 flex items-center justify-between gap-4">
              <p className="text-sm font-semibold text-foreground">Theme</p>
              <div className="flex bg-background border border-border rounded-lg p-1">
                {(['dark', 'light', 'system'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => {
                      update({ appearance: { ...settings.appearance, theme: t } });
                      showToast('Preferences saved');
                    }}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold capitalize transition-colors ${
                      settings.appearance.theme === t
                        ? 'bg-rally-blue text-white'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div className="p-5 flex items-center justify-between gap-4">
              <p className="text-sm font-semibold text-foreground">Units</p>
              <div className="flex bg-background border border-border rounded-lg p-1">
                {(['Metric', 'Imperial'] as const).map((u) => (
                  <button
                    key={u}
                    onClick={() => {
                      update({ appearance: { ...settings.appearance, units: u } });
                      showToast('Preferences saved');
                    }}
                    className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                      settings.appearance.units === u
                        ? 'bg-rally-blue text-white'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {u}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ABOUT */}
        <section className="space-y-3">
          <h2 className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">About</h2>
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-sm font-bold text-foreground">RALLY</p>
            <p className="text-xs text-muted-foreground mt-1 mb-3">AI-powered group travel safety and coordination platform.</p>
            <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <span>Version 1.0.0</span>
              <span>·</span>
              <span className="hover:text-foreground transition-colors cursor-pointer">Privacy</span>
              <span>·</span>
              <span className="hover:text-foreground transition-colors cursor-pointer">About</span>
            </div>
          </div>
        </section>

        <section className="pt-2">
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-red-500/30 bg-red-500/10 text-red-400 text-sm font-bold hover:bg-red-500/20 transition-colors"
          >
            <LogOut className="w-4 h-4" /> Log Out
          </button>
        </section>
      </div>

      {/* Edit Profile Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-card border border-border rounded-2xl w-full max-w-sm shadow-xl p-6 relative animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-foreground mb-4">Edit Profile</h3>
            
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-muted-foreground/80 tracking-wider uppercase mb-1.5 block">
                  Display Name
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  disabled={isSaving}
                  className="w-full bg-background border border-border rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:border-rally-blue transition-colors"
                />
              </div>
              
              <div>
                <label className="text-xs font-bold text-muted-foreground/80 tracking-wider uppercase mb-1.5 block">
                  Avatar
                </label>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-rally-blue/15 border border-rally-blue/30 text-rally-blue font-bold flex items-center justify-center text-lg">
                    {editName ? editName.charAt(0).toUpperCase() : 'U'}
                  </div>
                  <button type="button" disabled className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-semibold text-muted-foreground cursor-not-allowed">
                    Upload / Change
                  </button>
                </div>
              </div>

              {editError && (
                <p className="text-sm font-medium text-red-400">{editError}</p>
              )}
            </div>

            <div className="flex items-center gap-3 mt-8">
              <button
                onClick={() => setIsEditModalOpen(false)}
                disabled={isSaving}
                className="flex-1 px-4 py-2.5 rounded-xl border border-border text-foreground text-sm font-bold hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveProfile}
                disabled={isSaving}
                className="flex-1 px-4 py-2.5 rounded-xl bg-rally-blue text-white text-sm font-bold hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toasts */}
      {toastMessage && createPortal(
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] animate-in slide-in-from-bottom-5 fade-in duration-300">
          <div className="bg-foreground text-background px-4 py-2.5 rounded-full shadow-lg flex items-center gap-2">
            <Check className="w-4 h-4" />
            <span className="text-sm font-semibold">{toastMessage}</span>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
