'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Users, Copy, Check, MoreVertical, ShieldCheck, MapPin, Search } from 'lucide-react';
import RequireGroup from '@/components/dashboard/RequireGroup';
import Topbar from '@/components/dashboard/Topbar';
import ConfirmModal from '@/components/dashboard/ConfirmModal';
import { groupService } from '@/lib/mock/groupService';
import type { Member, Group } from '@/lib/mock/types';
import { supabase } from '@/lib/supabase';

function MembersContent({ group }: { group: Group }) {
  const router = useRouter();
  const [copied, setCopied] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showRemoveModal, setShowRemoveModal] = useState<{ member: Member | null }>({ member: null });
  const [showLeaveModal, setShowLeaveModal] = useState(false);
  const [actualName, setActualName] = useState('User');

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user) {
        setActualName(user.user_metadata?.full_name || user.user_metadata?.name || 'User');
      }
    });
  }, []);

  const me = group.members.find((m) => m.isCurrentUser);
  const isLeader = me?.role === 'Leader';

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(group.joinCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      // Fallback for toast if missing
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  const handleRemoveMember = async () => {
    if (showRemoveModal.member) {
      await groupService.removeMember(showRemoveModal.member.id);
      setShowRemoveModal({ member: null });
    }
  };

  const handleLeaveRally = async () => {
    if (isLeader) {
      // In a real app we'd prompt to transfer leadership
      // For Milestone 3, Option B: assume it handles it automatically or we just leave.
      // But prompt says: "If leadership transfer is not implemented yet, show: 'Transfer leadership before leaving this RALLY.'"
      alert('Transfer leadership before leaving this RALLY.');
      setShowLeaveModal(false);
      return;
    }
    await groupService.leaveGroup();
    router.push('/dashboard');
  };

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Topbar group={group} />

      <div className="flex-1 p-4 md:p-6 lg:p-8 space-y-6 max-w-4xl mx-auto w-full">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Members</h1>
            <p className="text-sm text-muted-foreground mt-1">Manage your RALLY members</p>
          </div>
          <button
            onClick={() => setShowInviteModal(true)}
            className="px-4 py-2.5 rounded-lg bg-rally-blue/10 border border-rally-blue/30 text-rally-blue text-sm font-semibold hover:bg-rally-blue/20 transition-colors shrink-0"
          >
            Invite Members
          </button>
        </div>

        {/* RALLY INFO CARD */}
        <div className="rounded-2xl border border-border bg-card p-5 md:p-6 space-y-5">
          <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase">Rally</p>
          <div>
            <h2 className="text-xl font-bold text-foreground mb-3">{group.name}</h2>
            <div className="flex items-center gap-6 text-sm text-foreground">
              <span className="flex items-center gap-2">
                <Users className="w-4 h-4 text-muted-foreground" />
                {group.members.length} {group.members.length === 1 ? 'member' : 'members'}
              </span>
              {group.destination && (
                <span className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-muted-foreground" />
                  {group.destination}
                </span>
              )}
            </div>
          </div>
          
          <div className="pt-4 border-t border-border">
            <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase mb-2">Join Code</p>
            <div className="flex items-center justify-between gap-4 bg-background p-3 rounded-xl border border-border">
              <code className="text-sm font-mono text-rally-blue font-bold px-2">{group.joinCode}</code>
              <button
                onClick={copyCode}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold text-foreground hover:bg-white/5 transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>
        </div>

        {/* MEMBERS LIST */}
        <div className="space-y-3">
          <p className="text-[10px] font-bold text-muted-foreground/60 tracking-[0.15em] uppercase px-2">Members</p>
          <div className="flex flex-col gap-3">
            {group.members.map((member) => (
              <div key={member.id} className="flex items-center justify-between p-4 rounded-2xl border border-border bg-card hover:border-border/80 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-11 h-11 rounded-full bg-rally-blue/15 border border-rally-blue/30 text-rally-blue font-bold flex items-center justify-center text-sm uppercase">
                    {(member.isCurrentUser ? actualName : member.name).charAt(0)}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {member.isCurrentUser ? actualName : member.name}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {member.isCurrentUser && <span className="font-medium text-foreground mr-1.5">You ·</span>}
                      {member.role}
                    </p>
                  </div>
                </div>

                {isLeader && !member.isCurrentUser && (
                  <div className="relative group/menu">
                    <button className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors">
                      <MoreVertical className="w-4 h-4" />
                    </button>
                    {/* Dropdown Menu using hover for simplicity, ideally a Radix dropdown */}
                    <div className="absolute right-0 top-full mt-1 hidden group-hover/menu:block w-48 bg-card border border-border rounded-xl shadow-xl overflow-hidden z-50">
                      <button 
                        onClick={() => setShowRemoveModal({ member })}
                        className="w-full text-left px-4 py-3 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        Remove from RALLY
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            
            {group.members.length === 0 && (
              <div className="text-center p-8 border border-border rounded-2xl bg-card text-muted-foreground">
                <p className="text-sm font-medium">No members found.</p>
              </div>
            )}
          </div>
        </div>

        {/* LEAVE RALLY */}
        <div className="pt-6 border-t border-border mt-8">
          <button
            onClick={() => setShowLeaveModal(true)}
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm font-bold hover:bg-red-500/20 transition-colors"
          >
            Leave RALLY
          </button>
        </div>
      </div>

      {/* MODALS */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-md shadow-xl relative animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold text-foreground mb-4">Invite members</h3>
            <p className="text-sm text-muted-foreground mb-6">Share this code with your group:</p>
            
            <div className="flex items-center justify-between gap-4 bg-background p-4 rounded-xl border border-border mb-6">
              <code className="text-lg font-mono text-rally-blue font-bold px-2">{group.joinCode}</code>
              <button
                onClick={copyCode}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-white/5 text-xs font-semibold text-foreground hover:bg-white/10 transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            
            <p className="text-sm text-muted-foreground mb-6">Anyone with this code can join your RALLY.</p>
            
            <button
              onClick={() => setShowInviteModal(false)}
              className="w-full py-2.5 rounded-lg bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
            >
              Done
            </button>
          </div>
        </div>
      )}

      {showRemoveModal.member && (
        <ConfirmModal
          icon={Users}
          title="Remove member?"
          description={`Remove ${showRemoveModal.member.name} from this RALLY?`}
          confirmLabel="Remove"
          busy={false}
          onCancel={() => setShowRemoveModal({ member: null })}
          onConfirm={handleRemoveMember}
        />
      )}

      {showLeaveModal && (
        <ConfirmModal
          icon={ShieldCheck}
          title="Leave this RALLY?"
          description="You will no longer have access to this group's live trip."
          confirmLabel="Leave RALLY"
          busy={false}
          onCancel={() => setShowLeaveModal(false)}
          onConfirm={handleLeaveRally}
        />
      )}
    </div>
  );
}

export default function MembersPage() {
  return (
    <RequireGroup>
      {(group) => <MembersContent group={group} />}
    </RequireGroup>
  );
}
