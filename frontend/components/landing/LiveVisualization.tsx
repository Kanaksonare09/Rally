'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Shield, Radio, Activity } from 'lucide-react';

export default function LiveVisualization() {
  const [progress, setProgress] = useState(45);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => (prev >= 100 ? 0 : prev + 0.3));
    }, 100);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="py-28 md:py-36 px-4 sm:px-6 md:px-12 bg-background border-t border-white/10 overflow-hidden">
      <div className="max-w-6xl mx-auto space-y-16">
        
        {/* Header */}
        <div className="max-w-3xl mx-auto text-center space-y-4">
          <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
            LIVE INTELLIGENCE STREAM
          </div>

          <h2 className="text-3xl md:text-5xl md:text-6xl tracking-tight font-medium leading-[1.08] text-white">
            Everyone moves. <br />
            <span className="font-serif italic font-normal text-white/95">
              RALLY sees the difference.
            </span>
          </h2>
        </div>

        {/* Floating Natural UI Visual */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.7 }}
          className="relative rounded-[24px] bg-[#050507] border border-white/15 overflow-hidden shadow-[0_30px_90px_rgba(0,0,0,0.95)]"
        >
          {/* Top Bar */}
          <div className="px-6 py-4 border-b border-white/10 bg-[#08080A]/90 backdrop-blur-md flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] tracking-wider uppercase font-semibold">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                ACTIVE STREAM • 6 MEMBERS
              </span>
            </div>

            <div className="flex items-center gap-4 text-white/70">
              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.03] border border-white/10 text-[11px]">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                <span>Group Health <strong className="text-white">96%</strong></span>
              </div>
              <span className="text-amber-400 text-[11px] font-semibold flex items-center gap-1.5 bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                MAYALAG: 180m
              </span>
            </div>
          </div>

          {/* Live Map Area */}
          <div className="relative min-h-[440px] sm:min-h-[500px] w-full bg-[#050608] flex items-center justify-center p-6 select-none overflow-hidden">
            
            {/* Ambient Background Grid */}
            <div className="absolute inset-0 bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:28px_28px] opacity-15 pointer-events-none" />

            {/* Route Line SVG */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 1000 500">
              <defs>
                <linearGradient id="liveGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#38bdf8" />
                  <stop offset="50%" stopColor="#22d3ee" />
                  <stop offset="100%" stopColor="#34d399" />
                </linearGradient>
              </defs>

              {/* Planned Route Line */}
              <path
                d="M 100 380 C 250 340, 400 240, 550 200 C 700 160, 800 120, 900 80"
                fill="none"
                stroke="rgba(255, 255, 255, 0.12)"
                strokeWidth="5"
                strokeLinecap="round"
              />
              {/* Animated Dash Path */}
              <path
                d="M 100 380 C 250 340, 400 240, 550 200 C 700 160, 800 120, 900 80"
                fill="none"
                stroke="url(#liveGradient)"
                strokeWidth="3"
                strokeLinecap="round"
                strokeDasharray="6 6"
                className="animate-[dash_20s_linear_infinite]"
              />

              {/* Waypoint Text */}
              <text x="100" y="410" fill="rgba(255,255,255,0.5)" fontSize="11" fontFamily="monospace">BASECAMP (0.0km)</text>
              <text x="900" y="60" fill="#34d399" fontSize="11" fontFamily="monospace" fontWeight="bold">DESTINATION (18.4km)</text>
            </svg>

            {/* Member Position Markers Floating on Route */}
            <div className="relative w-full h-full max-w-4xl mx-auto flex items-center justify-center font-mono">
              
              {/* Member 1: Maya (Separated/Lagging behind) */}
              <div 
                className="absolute transition-all duration-700 ease-out"
                style={{ left: `${12 + (progress * 0.4)}%`, top: `${70 - (progress * 0.22)}%` }}
              >
                <div className="relative flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.9)] animate-pulse" />
                  <div className="px-2.5 py-1 rounded-md bg-[#0A0D14]/90 border border-amber-500/40 text-[11px] font-mono text-amber-200 whitespace-nowrap backdrop-blur-md shadow-lg flex items-center gap-1.5">
                    <span className="font-semibold">Maya</span>
                    <span className="text-[10px] text-amber-400">180m behind</span>
                  </div>
                </div>
              </div>

              {/* Member 2: Alex */}
              <div 
                className="absolute transition-all duration-700 ease-out"
                style={{ left: `${28 + (progress * 0.48)}%`, top: `${56 - (progress * 0.28)}%` }}
              >
                <div className="relative flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.9)]" />
                  <div className="px-2.5 py-1 rounded-md bg-[#0A0D14]/90 border border-white/15 text-[11px] text-white/90 whitespace-nowrap backdrop-blur-md shadow-lg">
                    <span className="font-semibold">Alex</span>
                  </div>
                </div>
              </div>

              {/* Member 3: YOU (Lead Spotlight) */}
              <div 
                className="absolute transition-all duration-700 ease-out z-30"
                style={{ left: `${50 + (progress * 0.42)}%`, top: `${36 - (progress * 0.3)}%` }}
              >
                <div className="relative flex flex-col items-center">
                  <div className="relative flex items-center justify-center">
                    <span className="absolute w-10 h-10 rounded-full border border-white/50 animate-ping" />
                    <span className="absolute w-7 h-7 rounded-full bg-white/20 blur-sm" />
                    <div className="w-4 h-4 rounded-full bg-white border-2 border-cyan-400 shadow-[0_0_20px_rgba(255,255,255,1)] flex items-center justify-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-black" />
                    </div>
                  </div>
                  <div className="mt-1 px-2.5 py-0.5 rounded bg-white text-black text-[10px] font-bold uppercase tracking-wider shadow-2xl border border-white">
                    YOU
                  </div>
                </div>
              </div>

              {/* Member 4: Ben */}
              <div 
                className="absolute transition-all duration-700 ease-out"
                style={{ left: `${65 + (progress * 0.35)}%`, top: `${24 - (progress * 0.25)}%` }}
              >
                <div className="relative flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.9)]" />
                  <div className="px-2.5 py-1 rounded-md bg-[#0A0D14]/90 border border-white/15 text-[11px] text-white/90 whitespace-nowrap backdrop-blur-md shadow-lg">
                    <span className="font-semibold">Ben</span>
                  </div>
                </div>
              </div>

            </div>

            {/* Bottom-Left Live Readout Box */}
            <div className="absolute bottom-4 left-4 z-20 font-mono">
              <div className="p-3.5 rounded-xl bg-[#080A0F]/90 border border-white/10 backdrop-blur-xl text-left max-w-xs shadow-2xl space-y-1">
                <div className="text-[10px] tracking-widest text-white/50 uppercase font-semibold">
                  TRIP TELEMETRY
                </div>
                <div className="text-sm font-bold text-white">
                  High Alpine Ridge
                </div>
                <div className="text-[11px] text-white/60">
                  ETA: <span className="text-white font-medium">32 min</span> &nbsp;•&nbsp; Dist: <span className="text-emerald-400 font-medium">{(18.4 * (1 - progress/100)).toFixed(1)} km</span>
                </div>
              </div>
            </div>

            {/* Bottom-Right Pulse Status */}
            <div className="absolute bottom-4 right-4 z-20 font-mono text-xs">
              <div className="px-3.5 py-2 rounded-xl bg-[#080A0F]/90 border border-white/10 backdrop-blur-xl text-white/70 flex items-center gap-2 shadow-2xl">
                <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
                <span>POLLING SUB-SECOND</span>
              </div>
            </div>

          </div>

        </motion.div>

      </div>
    </section>
  );
}
