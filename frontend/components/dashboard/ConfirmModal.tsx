'use client';

import { X } from 'lucide-react';

export default function ConfirmModal({
  icon: Icon,
  iconColorClass = 'text-rally-blue',
  iconBgClass = 'bg-rally-blue/10 border-rally-blue/30',
  title,
  description,
  cancelLabel = 'Cancel',
  confirmLabel,
  busyLabel,
  confirmClass = 'bg-foreground text-background hover:opacity-85',
  busy,
  onCancel,
  onConfirm,
  success,
  successContent,
  error,
}: {
  icon: React.ElementType;
  iconColorClass?: string;
  iconBgClass?: string;
  title: string;
  description: string;
  cancelLabel?: string;
  confirmLabel: string;
  busyLabel?: string;
  confirmClass?: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  success?: boolean;
  successContent?: React.ReactNode;
  /** Shown below the description when a previous confirm attempt failed
   * — the request itself already happened and was rejected by the
   * backend, so this always reflects a real error, never a guess. */
  error?: string | null;
}) {
  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => !busy && onCancel()} />

      <div className="relative w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-2xl">
        <button
          onClick={onCancel}
          disabled={busy}
          className="absolute top-4 right-4 text-muted-foreground hover:text-foreground disabled:opacity-50"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>

        {success ? (
          successContent
        ) : (
          <>
            <div className={`w-12 h-12 rounded-full border flex items-center justify-center mb-4 ${iconBgClass}`}>
              <Icon className={`w-6 h-6 ${iconColorClass}`} />
            </div>
            <h2 className="text-base font-semibold text-foreground mb-1.5">{title}</h2>
            <p className="text-sm text-muted-foreground mb-2">{description}</p>
            {error && <p className="text-xs text-red-400 mb-4">{error}</p>}

            <div className="flex items-center gap-3 mt-4">
              <button
                onClick={onCancel}
                disabled={busy}
                className="flex-1 py-2.5 rounded-lg border border-border text-sm font-semibold text-foreground hover:bg-white/5 transition-colors disabled:opacity-50"
              >
                {cancelLabel}
              </button>
              <button
                onClick={onConfirm}
                disabled={busy}
                className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-colors disabled:opacity-70 ${confirmClass}`}
              >
                {busy ? busyLabel ?? `${confirmLabel}…` : confirmLabel}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
