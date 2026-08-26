'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Play, Pause, RotateCcw, Clock, Navigation } from 'lucide-react';

export default function TripReplayDemo() {
  const [isPlaying, setIsPlaying] = useState(true);
  const [replayProgress, setReplayProgress] = useState(35);

  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setReplayProgress((prev) => (prev >= 100 ? 0 : prev + 0.5));
    }, 80);
    return () => clearInterval(interval);
  }, [isPlaying]);

  return (
    <section className="py-28 md:py-36 px-4 sm:px-6 md:px-12 bg-background border-t border-white/10">
      <div className="max-w-5xl mx-auto space-y-16">
        
        {/* Header */}
        <div className="max-w-2xl space-y-4">
          <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
            POST-TRIP RECAP & RECORD
          </div>

          <h2 className="text-3xl md:text-5xl md:text-6xl tracking-tight font-medium leading-[1.08] text-white">
            Every trip <br />
            <span className="font-serif italic font-normal text-white/95">
              leaves a trail.
            </span>
          </h2>
        </div>

        {/* Product Demo Simulation Box */}
        <div className="rounded-2xl bg-[#050507] border border-white/15 overflow-hidden shadow-2xl font-mono text-xs">
          
          {/* Replay Visual Screen */}
          <div className="relative min-h-[360px] w-full bg-[#050608] flex items-center justify-center p-6 select-none overflow-hidden">
            
            {/* Subtle Grid */}
            <div className="absolute inset-0 bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:24px_24px] opacity-10 pointer-events-none" />

            <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 800 400">
              {/* Path base line */}
              <path
                d="M 80 320 C 200 300, 300 150, 450 200 C 600 250, 680 120, 720 80"
                fill="none"
                stroke="rgba(255, 255, 255, 0.12)"
                strokeWidth="4"
              />
              {/* Active Replay Trail */}
              <path
                d="M 80 320 C 200 300, 300 150, 450 200 C 600 250, 680 120, 720 80"
                fill="none"
                stroke="#34d399"
                strokeWidth="3.5"
                strokeDasharray="1000"
                strokeDashoffset={1000 - (replayProgress / 100) * 1000}
                strokeLinecap="round"
              />

              {/* Waypoints */}
              <circle cx="80" cy="320" r="4" fill="#38bdf8" />
              <text x="80" y="345" fill="rgba(255,255,255,0.6)" fontSize="10">09:42 DEPARTURE</text>

              <circle cx="450" cy="200" r="4" fill="#fbbf24" />
              <text x="450" y="225" fill="rgba(255,255,255,0.6)" fontSize="10">10:30 REGROUP STOP</text>

              <circle cx="720" cy="80" r="4" fill="#34d399" />
              <text x="720" y="65" fill="#34d399" fontSize="10" fontWeight="bold">11:18 FINISH</text>
            </svg>

            {/* Dynamic Moving Marker */}
            <div 
              className="absolute transition-all duration-300 pointer-events-none"
              style={{ 
                left: `${10 + (replayProgress * 0.8)}%`, 
                top: `${80 - (replayProgress * 0.7)}%` 
              }}
            >
              <div className="relative flex items-center gap-2">
                <div className="w-3.5 h-3.5 rounded-full bg-white border-2 border-emerald-400 shadow-[0_0_15px_rgba(52,211,153,1)]" />
                <span className="px-2 py-0.5 rounded bg-white text-black font-mono text-[10px] font-bold">
                  REPLAY
                </span>
              </div>
            </div>

            {/* Replay Details Panel (Bottom Left) */}
            <div className="absolute bottom-4 left-4 p-3.5 rounded-xl bg-[#080A0F]/90 border border-white/10 backdrop-blur-xl text-left max-w-xs space-y-1">
              <div className="text-[10px] text-white/40 uppercase tracking-widest font-semibold">TRIP RECAP</div>
              <div className="text-sm font-bold text-white">48.2 km • 1h 36m</div>
              <div className="text-[11px] text-emerald-400">Safety Score: 98/100</div>
            </div>

          </div>

          {/* Playback Controls Bar */}
          <div className="px-6 py-4 bg-[#080809] border-t border-white/10 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 border border-white/15 flex items-center justify-center text-white transition-colors"
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
              </button>
              <button
                onClick={() => setReplayProgress(0)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-white/70 hover:text-white transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Playback Progress Slider: 09:42 ━━━━━●━━━━ 11:18 */}
            <div className="flex-1 max-w-md flex items-center gap-3 text-white/60">
              <span className="text-[11px] text-white/40">09:42</span>
              <input
                type="range"
                min="0"
                max="100"
                value={replayProgress}
                onChange={(e) => setReplayProgress(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-white"
              />
              <span className="text-[11px] text-white/40">11:18</span>
            </div>
          </div>

        </div>

      </div>
    </section>
  );
}
