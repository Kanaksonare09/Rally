'use client';

import Link from 'next/link';
import { Compass, Lock } from 'lucide-react';

export default function EmptyRallyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
      <div className="w-14 h-14 rounded-2xl bg-rally-blue/10 border border-rally-blue/30 flex items-center justify-center text-rally-blue mb-6">
        <Compass className="w-7 h-7" />
      </div>

      <h1 className="text-xl font-semibold text-foreground mb-2">Start your first RALLY</h1>
      <p className="text-sm text-muted-foreground max-w-sm mb-8">
        Create a group for your journey or join an existing group to start moving together.
      </p>

      <div className="flex items-center gap-3 mb-8">
        <Link
          href="/create-group"
          className="px-6 py-2.5 rounded-xl bg-foreground text-background text-sm font-semibold hover:opacity-85 transition-opacity"
        >
          Create RALLY
        </Link>
        <Link
          href="/join-group"
          className="px-6 py-2.5 rounded-xl border border-border text-foreground text-sm font-semibold hover:bg-white/5 transition-colors"
        >
          Join RALLY
        </Link>
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground/70">
        <Lock className="w-3.5 h-3.5" />
        <span>Your location is shared only with your RALLY members.</span>
      </div>
    </div>
  );
}
