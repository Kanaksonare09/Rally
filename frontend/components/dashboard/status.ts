import type { SafetyStatus } from '@/lib/mock/types';

export const STATUS_STYLE: Record<
  SafetyStatus,
  { label: string; dot: string; text: string; bg: string; border: string; hex: string }
> = {
  safe: {
    label: 'Safe',
    dot: 'bg-emerald-400',
    text: 'text-emerald-400',
    bg: 'bg-emerald-400/10',
    border: 'border-emerald-400/30',
    hex: '#34D399',
  },
  warning: {
    label: 'Warning',
    dot: 'bg-amber-400',
    text: 'text-amber-400',
    bg: 'bg-amber-400/10',
    border: 'border-amber-400/30',
    hex: '#FBBF24',
  },
  critical: {
    label: 'Critical',
    dot: 'bg-red-500',
    text: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    hex: '#F87171',
  },
  offline: {
    label: 'Offline',
    dot: 'bg-slate-500',
    text: 'text-slate-400',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/30',
    hex: '#94A3B8',
  },
};
