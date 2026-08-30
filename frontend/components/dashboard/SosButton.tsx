'use client';

import { useState } from 'react';
import { Siren, AlertTriangle } from 'lucide-react';
import { groupService } from '@/lib/group/groupService';
import { friendlyErrorMessage } from '@/lib/api/errors';
import ConfirmModal from './ConfirmModal';

/**
 * SOS is safety-critical (Phase 13, item 19): "Sending…" is shown the
 * instant the button is pressed, but "SOS Active"/success is only ever
 * shown once the backend has confirmed the request — a failed request
 * shows a clear error with a retry, never a silent success. Duplicate
 * presses are safe: the backend is idempotent for an already-ACTIVE SOS
 * (see backend/app/sos/service.py) and always returns the SAME
 * emergency rather than creating a second one.
 */
export default function SosButton() {
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSend = async () => {
    setSending(true);
    setError(null);
    try {
      await groupService.sendSOS();
      setSending(false);
      setSent(true);
      setTimeout(() => {
        setOpen(false);
        setSent(false);
      }, 1400);
    } catch (err) {
      setSending(false);
      setError(friendlyErrorMessage(err));
    }
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
          icon={error ? AlertTriangle : Siren}
          iconColorClass="text-red-400"
          iconBgClass="bg-red-500/10 border-red-500/30"
          title={error ? 'SOS could not be sent' : 'Send Emergency Alert?'}
          description={error ?? 'Your current location will be shared with all group members.'}
          confirmLabel={error ? 'Retry' : 'Send SOS'}
          busyLabel="Sending…"
          confirmClass="bg-red-500 text-white hover:bg-red-400"
          busy={sending}
          onCancel={() => {
            setOpen(false);
            setError(null);
          }}
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
