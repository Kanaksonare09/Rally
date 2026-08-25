'use client';

import { useState } from 'react';
import { Siren } from 'lucide-react';
import { groupService } from '@/lib/mock/groupService';
import ConfirmModal from './ConfirmModal';

export default function SosButton() {
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSend = async () => {
    setSending(true);
    await groupService.sendSOS();
    setSending(false);
    setSent(true);
    setTimeout(() => {
      setOpen(false);
      setSent(false);
    }, 1400);
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Send emergency SOS"
        className="fixed z-[1500] bottom-20 md:bottom-8 right-5 md:right-8 w-14 h-14 rounded-full bg-red-500 text-white shadow-2xl shadow-red-500/40 flex items-center justify-center hover:scale-105 active:scale-95 transition-transform"
      >
        <Siren className="w-6 h-6" />
      </button>

      {open && (
        <ConfirmModal
          icon={Siren}
          iconColorClass="text-red-400"
          iconBgClass="bg-red-500/10 border-red-500/30"
          title="Send Emergency Alert?"
          description="Your current location will be shared with all group members."
          confirmLabel="Send SOS"
          busyLabel="Sending…"
          confirmClass="bg-red-500 text-white hover:bg-red-400"
          busy={sending}
          onCancel={() => setOpen(false)}
          onConfirm={handleSend}
          success={sent}
          successContent={
            <div className="flex flex-col items-center text-center gap-3 py-4">
              <div className="w-12 h-12 rounded-full bg-emerald-400/10 border border-emerald-400/30 flex items-center justify-center">
                <Siren className="w-6 h-6 text-emerald-400" />
              </div>
              <p className="text-sm font-semibold text-foreground">SOS sent to your group</p>
            </div>
          }
        />
      )}
    </>
  );
}
