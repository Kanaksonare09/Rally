'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Minus, Plus, Copy, Check, ArrowRight, Users, AlertCircle } from 'lucide-react';
import { groupService, buildPreviewGroup } from '@/lib/group/groupService';
import { friendlyErrorMessage } from '@/lib/api/errors';
import LiveMap from '@/components/map/LiveMap';

const DESTINATIONS = ['Solang Valley', 'Rohtang Pass', 'Kasol', 'Manali', 'Leh Ladakh', 'Spiti Valley'];

export default function CreateGroupPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [destination, setDestination] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [maxMembers, setMaxMembers] = useState(5);
  const [submitting, setSubmitting] = useState(false);
  const [joinCode, setJoinCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredDestinations = DESTINATIONS.filter((d) =>
    d.toLowerCase().includes(destination.toLowerCase())
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !destination.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const group = await groupService.createGroup({ name: name.trim(), destination: destination.trim(), maxMembers });
      setJoinCode(group.joinCode);
    } catch (err) {
      setError(friendlyErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = () => {
    if (!joinCode) return;
    navigator.clipboard.writeText(joinCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleInvite = async () => {
    if (!joinCode) return;
    if (typeof navigator !== 'undefined' && 'share' in navigator) {
      try {
        await navigator.share({ title: 'Join my Rally', text: `Join my group on RALLY with code ${joinCode}` });
        return;
      } catch {
        // user cancelled or share unsupported — fall through to copy
      }
    }
    handleCopy();
  };

  const previewGroup = buildPreviewGroup({ name, destination, maxMembers });

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row">
      <div className="w-full lg:w-[440px] shrink-0 border-r border-border flex flex-col justify-between px-6 sm:px-10 py-10 min-h-screen">
        <div>
          <Link href="/" className="inline-flex items-center mb-8">
            <img
              src="/assets/new-rally-logo-transparent.png"
              alt="RALLY"
              className="h-7.5 w-auto object-contain opacity-90 hover:opacity-100 transition-opacity"
            />
          </Link>

        {!joinCode ? (
          <>
            <h1 className="text-2xl font-semibold text-foreground mb-2">Create your Rally</h1>
            <p className="text-sm text-muted-foreground mb-8">
              Bring everyone together and keep the journey connected.
            </p>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Group Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Manali Adventure"
                  required
                  className="w-full bg-card border border-border rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-rally-blue transition-colors"
                />
              </div>

              <div className="space-y-1.5 relative">
                <label className="text-xs font-semibold text-muted-foreground">Destination</label>
                <input
                  value={destination}
                  onChange={(e) => {
                    setDestination(e.target.value);
                    setShowSuggestions(true);
                  }}
                  onFocus={() => setShowSuggestions(true)}
                  onBlur={() => setTimeout(() => setShowSuggestions(false), 120)}
                  placeholder="Solang Valley"
                  required
                  autoComplete="off"
                  className="w-full bg-card border border-border rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-rally-blue transition-colors"
                />
                {showSuggestions && filteredDestinations.length > 0 && (
                  <div className="absolute z-10 top-full mt-1.5 w-full bg-card border border-border rounded-xl overflow-hidden shadow-2xl">
                    {filteredDestinations.map((d) => (
                      <button
                        type="button"
                        key={d}
                        onMouseDown={() => {
                          setDestination(d);
                          setShowSuggestions(false);
                        }}
                        className="w-full text-left px-4 py-2.5 text-sm text-foreground hover:bg-white/5 transition-colors"
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Maximum Members</label>
                <div className="flex items-center justify-between bg-card border border-border rounded-xl px-4 py-2.5">
                  <button
                    type="button"
                    onClick={() => setMaxMembers((m) => Math.max(2, m - 1))}
                    aria-label="Decrease maximum members"
                    className="w-8 h-8 rounded-lg border border-border flex items-center justify-center text-foreground hover:bg-white/5 transition-colors"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Users className="w-4 h-4 text-muted-foreground" />
                    {maxMembers}
                  </span>
                  <button
                    type="button"
                    onClick={() => setMaxMembers((m) => Math.min(20, m + 1))}
                    aria-label="Increase maximum members"
                    className="w-8 h-8 rounded-lg border border-border flex items-center justify-center text-foreground hover:bg-white/5 transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {error && (
                <p className="flex items-center gap-1.5 text-xs text-red-400 px-1">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {error}
                </p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-3.5 rounded-xl bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2 mt-2"
              >
                {submitting ? 'Creating…' : 'Create Rally'}
                {!submitting && <ArrowRight className="w-4 h-4" />}
              </button>
            </form>
          </>
        ) : (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-semibold text-foreground mb-2">Your Rally is ready</h1>
              <p className="text-sm text-muted-foreground">Share this code with your group members.</p>
            </div>

            <div className="rounded-2xl border border-rally-blue/30 bg-rally-blue/5 p-6 text-center">
              <p className="text-[11px] font-semibold text-muted-foreground tracking-wider mb-3">JOIN CODE</p>
              <p className="text-3xl sm:text-4xl font-bold tracking-[0.1em] text-rally-blue font-mono mb-4 break-all">
                {joinCode}
              </p>
              <button
                onClick={handleCopy}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-semibold text-foreground hover:bg-white/5 transition-colors"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied' : 'Copy code'}
              </button>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => router.push('/dashboard')}
                className="flex-1 py-3 rounded-xl bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
              >
                Go to Dashboard
              </button>
              <button
                onClick={handleInvite}
                className="flex-1 py-3 rounded-xl border border-border text-foreground text-sm font-semibold hover:bg-white/5 transition-colors"
              >
                Invite Members
              </button>
            </div>
          </div>
        )}
        </div>
      </div>

      <div className="hidden lg:block flex-1 relative p-6">
        <div className="h-full rounded-2xl overflow-hidden">
          <LiveMap group={previewGroup} />
        </div>
      </div>
    </div>
  );
}
