'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { groupService } from '@/lib/mock/groupService';

type Status = 'idle' | 'loading' | 'invalid' | 'success';

export default function JoinGroupPage() {
  const router = useRouter();
  const [code, setCode] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim() || status === 'loading') return;

    setStatus('loading');
    try {
      await groupService.joinGroup(code);
      setStatus('success');
      setTimeout(() => router.push('/dashboard'), 900);
    } catch (err) {
      setStatus('invalid');
      setError(err instanceof Error ? err.message : 'Something went wrong. Try again.');
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-6 py-12 relative overflow-hidden">
      <div className="absolute w-[500px] h-[500px] bg-rally-blue/10 blur-[120px] rounded-full pointer-events-none" />

      <div className="w-full max-w-sm relative z-10">
        <Link href="/" className="inline-flex items-center mb-10">
          <img src="/assets/rally-wordmark.png" alt="RALLY" className="h-6 w-auto" />
        </Link>

        {status === 'success' ? (
          <div className="text-center space-y-4 py-6">
            <div className="w-14 h-14 rounded-full bg-emerald-400/10 border border-emerald-400/30 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-foreground">You're in</h1>
              <p className="text-sm text-muted-foreground mt-1">Taking you to your dashboard…</p>
            </div>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-semibold text-foreground mb-2">Join a Rally</h1>
            <p className="text-sm text-muted-foreground mb-8">Enter the code shared by your group leader.</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <input
                  value={code}
                  onChange={(e) => {
                    setCode(e.target.value.toUpperCase());
                    if (status === 'invalid') setStatus('idle');
                  }}
                  placeholder="RALLY-X7K92"
                  autoComplete="off"
                  autoCapitalize="characters"
                  disabled={status === 'loading'}
                  className={`w-full bg-card border rounded-2xl px-5 py-5 text-center text-2xl font-mono font-bold tracking-[0.15em] text-foreground placeholder:text-muted-foreground/40 focus:outline-none transition-colors ${
                    status === 'invalid'
                      ? 'border-red-500/60 focus:border-red-500'
                      : 'border-border focus:border-rally-blue'
                  }`}
                />
                {status === 'invalid' && (
                  <p className="flex items-center gap-1.5 text-xs text-red-400 mt-2 px-1">
                    <XCircle className="w-3.5 h-3.5 shrink-0" /> {error}
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={status === 'loading' || !code.trim()}
                className="w-full py-3.5 rounded-xl bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {status === 'loading' ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Verifying…
                  </>
                ) : (
                  <>
                    Join Rally <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            <p className="text-center text-sm text-muted-foreground mt-8">
              <Link href="/create-group" className="font-semibold text-rally-blue hover:underline">
                Create a new Rally instead
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
