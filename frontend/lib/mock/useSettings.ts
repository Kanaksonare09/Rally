'use client';

import { useEffect, useState } from 'react';
import { settingsService, DEFAULT_SETTINGS } from './settingsService';
import type { Settings } from './types';

export function useSettings() {
  // Start with defaults on both server and client — the singleton reads
  // localStorage synchronously at import time, so reading it here in the
  // initializer would mismatch the server's render. Sync for real in effect.
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);

  useEffect(() => {
    setSettings(settingsService.get());
    return settingsService.subscribe(setSettings);
  }, []);

  const update = (patch: Partial<Settings>) => settingsService.update(patch);

  return { settings, update };
}
