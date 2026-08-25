import type { Settings } from './types';

const STORAGE_KEY = 'rally:settings';

export const DEFAULT_SETTINGS: Settings = {
  profile: { name: 'Keshav', email: 'keshav@rally.app' },
  notifications: {
    alerts: true,
    sos: true,
    connectivity: true,
    tripSummaries: false,
  },
  location: {
    sharing: true,
    accuracy: 'high',
    backgroundTracking: 'while_active',
  },
  safety: {
    alertSensitivity: 'medium',
    separationThresholdM: 150,
    routeDeviationThresholdM: 100,
  },
  appearance: {
    theme: 'dark',
  },
};

class MockSettingsService {
  private settings: Settings;
  private listeners = new Set<(settings: Settings) => void>();

  constructor() {
    this.settings = this.read();
  }

  private read(): Settings {
    if (typeof window === 'undefined') return DEFAULT_SETTINGS;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) return { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Settings) };
    } catch {
      // fall through to defaults
    }
    return DEFAULT_SETTINGS;
  }

  private persist() {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(this.settings));
  }

  get(): Settings {
    return this.settings;
  }

  update(patch: Partial<Settings>): Settings {
    this.settings = { ...this.settings, ...patch };
    this.persist();
    this.listeners.forEach((l) => l(this.settings));
    return this.settings;
  }

  subscribe(listener: (settings: Settings) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

export const settingsService = new MockSettingsService();
