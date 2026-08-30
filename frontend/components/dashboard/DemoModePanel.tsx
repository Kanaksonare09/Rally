'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { PlayCircle, Square, RotateCcw, Loader2, AlertCircle } from 'lucide-react';
import { SettingsSection } from './SettingsSection';
import { isDemoModeAvailable, getDemoStatus, resetDemo, startDemoScenario, stopDemoScenario } from '@/lib/api/demo';
import { friendlyErrorMessage } from '@/lib/api/errors';
import type { DemoStatusResponse } from '@/lib/api/types';

function humanizeScenario(scenario: string): string {
  return scenario
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

/**
 * Only ever talks to the backend's REAL demo endpoints
 * (backend/app/api/demo.py) — no second, frontend-only simulator (Phase
 * 13, item 43/51). The whole section only renders when the backend was
 * actually started with DEMO_MODE=true; `isDemoModeAvailable()` probes
 * that once (a genuine 404 when it's off, not an error).
 */
export default function DemoModePanel() {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [status, setStatus] = useState<DemoStatusResponse | null>(null);
  const [busyScenario, setBusyScenario] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshStatus = () => {
    getDemoStatus()
      .then(setStatus)
      .catch((err) => setError(friendlyErrorMessage(err)));
  };

  useEffect(() => {
    isDemoModeAvailable()
      .then((ok) => {
        setAvailable(ok);
        if (ok) refreshStatus();
      })
      .catch(() => setAvailable(false));
  }, []);

  if (available === null || available === false) return null;

  const handleStart = async (scenario: string) => {
    setBusyScenario(scenario);
    setError(null);
    try {
      await startDemoScenario(scenario);
      refreshStatus();
    } catch (err) {
      setError(friendlyErrorMessage(err));
    } finally {
      setBusyScenario(null);
    }
  };

  const handleStop = async (scenario: string) => {
    setBusyScenario(scenario);
    setError(null);
    try {
      await stopDemoScenario(scenario);
      refreshStatus();
    } catch (err) {
      setError(friendlyErrorMessage(err));
    } finally {
      setBusyScenario(null);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    setError(null);
    try {
      await resetDemo();
      refreshStatus();
    } catch (err) {
      setError(friendlyErrorMessage(err));
    } finally {
      setResetting(false);
    }
  };

  return (
    <SettingsSection title="Demo Mode" icon={PlayCircle}>
      <p className="text-xs text-muted-foreground -mt-2">
        Drives a real demo trip on the backend — not a frontend simulation. Open the{' '}
        <Link href="/dashboard" className="text-rally-blue hover:underline">
          dashboard
        </Link>{' '}
        to watch it live.
      </p>

      {error && (
        <p className="flex items-center gap-2 text-xs text-red-400">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {error}
        </p>
      )}

      {status?.running && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3.5 py-2.5">
          <div className="text-xs text-emerald-400">
            <p className="font-semibold">{status.scenario ? humanizeScenario(status.scenario) : 'Running'}</p>
            {status.tick != null && status.total_ticks != null && (
              <p className="text-emerald-400/80 mt-0.5">Tick {status.tick} / {status.total_ticks}</p>
            )}
          </div>
          <button
            onClick={() => status.scenario && void handleStop(status.scenario)}
            disabled={busyScenario === status.scenario}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold text-foreground hover:bg-white/5 transition-colors disabled:opacity-60"
          >
            <Square className="w-3 h-3" /> Stop
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        {(status?.available_scenarios ?? []).map((scenario) => (
          <button
            key={scenario}
            onClick={() => void handleStart(scenario)}
            disabled={busyScenario !== null || status?.running}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 text-foreground text-xs font-medium transition-colors disabled:opacity-50"
          >
            {busyScenario === scenario ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PlayCircle className="w-3.5 h-3.5 text-rally-blue" />}
            {humanizeScenario(scenario)}
          </button>
        ))}
      </div>

      <button
        onClick={() => void handleReset()}
        disabled={resetting}
        className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors disabled:opacity-60"
      >
        <RotateCcw className="w-3.5 h-3.5" /> {resetting ? 'Resetting…' : 'Reset demo group'}
      </button>
    </SettingsSection>
  );
}
