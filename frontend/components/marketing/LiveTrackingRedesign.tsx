'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Shield, 
  Play, 
  Pause, 
  RotateCcw,
  Radio,
  Users,
  ArrowRight,
  CheckCircle2,
  Navigation,
  Compass,
  Activity
} from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

// Member Mock Data for Live Map
const MEMBERS = [
  { id: '1', name: 'Rahul', status: '1 min behind', progress: 0.52, isYou: false, isLate: true },
  { id: '2', name: 'Keshav', status: 'Moving', progress: 0.68, isYou: false, isLate: false },
  { id: '3', name: 'Aditi', status: 'Moving', progress: 0.74, isYou: false, isLate: false },
  { id: '4', name: 'YOU', status: 'Moving', progress: 0.81, isYou: true, isLate: false },
  { id: '5', name: 'Priya', status: 'Moving', progress: 0.86, isYou: false, isLate: false },
];

const TIMELINE_STAGES = [
  {
    num: '01',
    label: 'START',
    title: 'Start',
    desc: 'The trip begins and the group becomes visible.',
  },
  {
    num: '02',
    label: 'MOVE',
    title: 'Move',
    desc: "Every member's position updates as they travel.",
  },
  {
    num: '03',
    label: 'UNDERSTAND',
    title: 'Understand',
    desc: 'See where everyone is relative to the planned route.',
  },
  {
    num: '04',
    label: 'ADAPT',
    title: 'Adapt',
    desc: 'The group can react when someone falls behind.',
  },
  {
    num: '05',
    label: 'ARRIVE',
    title: 'Arrive',
    desc: 'Everyone reaches the destination together.',
  },
];

export default function LiveTrackingRedesign() {
  const [isPlaying, setIsPlaying] = useState(true);
  const [progress, setProgress] = useState(68); // 0 to 100%
  const [activeStage, setActiveStage] = useState(1); // 0 to 4
  const [viewMode, setViewMode] = useState<'topo' | 'vector'>('topo');

  // Dynamic Telemetry State based on progress
  const currentSpeed = isPlaying ? Math.round(54 + Math.sin(progress / 4) * 6) : 0;
  const currentAlt = Math.round(2050 + (progress / 100) * 510);
  const currentHdg = Math.round((320 + progress / 2) % 360);
  const remainingDist = (14 * (1 - progress / 100)).toFixed(1);

  // Auto-play simulation slider
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setProgress((prev) => (prev >= 100 ? 0 : prev + 0.35));
    }, 100);
    return () => clearInterval(interval);
  }, [isPlaying]);

  return (
    <div className="bg-[#000000] text-white min-h-screen font-sans selection:bg-white/20 selection:text-white">
      {/* Top Navbar */}
      <Navbar />

      {/* 1. HERO SECTION */}
      <section className="pt-24 pb-16 sm:pt-32 sm:pb-24 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
        {/* Top Eyebrow Badge */}
        <motion.div 
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono tracking-[0.2em] text-white/70 uppercase mb-8"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          LIVE TRACKING
        </motion.div>

        {/* Main Headline */}
        <motion.h1 
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl md:text-[68px] font-medium tracking-tight text-white max-w-4xl leading-[1.08]"
        >
          See your whole group, <br />
          <span className="font-serif italic font-normal text-white/95 tracking-normal">
            moving together.
          </span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p 
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-6 text-sm sm:text-lg text-white/60 max-w-2xl font-normal leading-relaxed"
        >
          One shared map for the whole trip — every member's position, your planned route, and the destination, all in one place.
        </motion.p>

        {/* Action CTA Buttons */}
        <motion.div 
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-10 flex flex-wrap items-center justify-center gap-4 font-mono text-xs"
        >
          <Link
            href="/create-group"
            className="px-7 py-3.5 min-h-[44px] rounded-full bg-white text-black font-semibold tracking-wider uppercase hover:bg-white/90 transition-all duration-200 shadow-[0_0_25px_rgba(255,255,255,0.2)] hover:scale-[1.02] flex items-center"
          >
            START A RALLY
          </Link>
          <button
            onClick={() => {
              const el = document.getElementById('live-map-showcase');
              el?.scrollIntoView({ behavior: 'smooth' });
            }}
            className="px-7 py-3.5 min-h-[44px] rounded-full bg-white/[0.04] border border-white/20 text-white font-semibold tracking-wider uppercase hover:bg-white/[0.08] hover:border-white/40 transition-all duration-200 flex items-center"
          >
            SEE IT IN ACTION
          </button>
        </motion.div>
      </section>

      {/* 2. HERO → MAP TRANSITION & MAP SHOWCASE */}
      <section id="live-map-showcase" className="px-4 sm:px-6 max-w-6xl mx-auto mb-28 scroll-mt-24">
        {/* Subtle Label Above Map */}
        <div className="flex items-center justify-between font-mono text-xs text-white/40 tracking-[0.2em] uppercase mb-4 px-2">
          <span>LIVE GROUP VIEW</span>
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            5 MEMBERS ONLINE
          </span>
        </div>

        {/* Interactive Map Visual Container */}
        <div className="relative rounded-[24px] bg-[#050507] border border-white/10 overflow-hidden shadow-[0_25px_80px_rgba(0,0,0,0.9)]">
          
          {/* Top Control Bar inside Map */}
          <div className="px-5 py-4 border-b border-white/10 bg-[#080809]/90 backdrop-blur-md flex flex-wrap items-center justify-between gap-3 relative z-20 font-mono text-xs">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] tracking-wider uppercase">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                LIVE • 5 MEMBERS
              </span>

              {/* View Switcher: Topo vs Vector */}
              <div className="flex items-center bg-white/5 border border-white/10 rounded-full p-0.5">
                <button
                  onClick={() => setViewMode('topo')}
                  className={`px-3 py-1 rounded-full text-[10px] transition-all ${
                    viewMode === 'topo' ? 'bg-white text-black font-semibold' : 'text-white/60 hover:text-white'
                  }`}
                >
                  TOPO MAP
                </button>
                <button
                  onClick={() => setViewMode('vector')}
                  className={`px-3 py-1 rounded-full text-[10px] transition-all ${
                    viewMode === 'vector' ? 'bg-white text-black font-semibold' : 'text-white/60 hover:text-white'
                  }`}
                >
                  GRID VIEW
                </button>
              </div>
            </div>

            {/* Right Health Status Badge */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/[0.03] border border-white/10 text-[11px] text-white/80">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                <span>Group Health <strong className="text-white">98%</strong></span>
                <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 font-semibold uppercase tracking-wider ml-1">
                  LOW RISK
                </span>
              </div>
            </div>
          </div>

          {/* Main Map Visual Area */}
          <div className="relative min-h-[460px] sm:min-h-[520px] w-full bg-[#050608] overflow-hidden flex items-center justify-center p-6 select-none">
            
            {/* Topo Texture Background */}
            {viewMode === 'topo' ? (
              <div className="absolute inset-0 opacity-30 pointer-events-none">
                <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 1000 600">
                  <defs>
                    <linearGradient id="routeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
                      <stop offset="50%" stopColor="#22d3ee" stopOpacity="1" />
                      <stop offset="100%" stopColor="#34d399" stopOpacity="0.9" />
                    </linearGradient>
                    <radialGradient id="mapGlow" cx="50%" cy="50%" r="50%">
                      <stop offset="0%" stopColor="#14b8a6" stopOpacity="0.12" />
                      <stop offset="100%" stopColor="#000000" stopOpacity="0" />
                    </radialGradient>
                  </defs>
                  
                  {/* Topo contour lines */}
                  <path d="M 0,100 Q 200,80 400,160 T 800,120 T 1000,180" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
                  <path d="M 0,200 Q 250,150 500,240 T 900,200 T 1000,260" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="1" />
                  <path d="M 0,300 Q 180,260 450,330 T 850,290 T 1000,340" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                  <path d="M 0,400 Q 300,340 600,420 T 950,380 T 1000,460" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
                  
                  <rect width="1000" height="600" fill="url(#mapGlow)" />
                </svg>
              </div>
            ) : (
              <div className="absolute inset-0 bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:24px_24px] opacity-15 pointer-events-none" />
            )}

            {/* Route Vector Line */}
            <svg className="absolute inset-0 w-full h-full overflow-visible pointer-events-none">
              <path
                d="M 120 420 C 240 380, 360 280, 500 240 C 640 200, 760 140, 880 100"
                fill="none"
                stroke="rgba(255, 255, 255, 0.12)"
                strokeWidth="6"
                strokeLinecap="round"
              />
              <path
                d="M 120 420 C 240 380, 360 280, 500 240 C 640 200, 760 140, 880 100"
                fill="none"
                stroke="url(#routeGradient)"
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeDasharray="6 6"
                className="animate-[dash_20s_linear_infinite]"
              />

              {/* Waypoint Labels */}
              <g className="text-white/60 text-[10px] font-mono">
                <circle cx="120" cy="420" r="4" fill="#38bdf8" />
                <text x="120" y="445" textAnchor="middle" fill="rgba(255,255,255,0.7)">START (MANALI)</text>

                <circle cx="500" cy="240" r="4" fill="#22d3ee" />
                <text x="500" y="265" textAnchor="middle" fill="rgba(255,255,255,0.7)">CHECKPOINT (Palchan)</text>

                <circle cx="880" cy="100" r="4" fill="#34d399" />
                <text x="880" y="80" textAnchor="middle" fill="#34d399" fontWeight="bold">DESTINATION (Solang Valley)</text>
              </g>
            </svg>

            {/* Member Position Markers */}
            <div className="relative w-full h-full max-w-4xl mx-auto flex items-center justify-center">

              {/* Member 1: Rahul (Lagging behind) */}
              <div 
                className="absolute transition-all duration-700 ease-out"
                style={{ left: `${15 + (progress * 0.45)}%`, top: `${72 - (progress * 0.25)}%` }}
              >
                <div className="relative flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.9)] animate-pulse" />
                  <div className="px-2.5 py-1 rounded-md bg-[#0A0D14]/90 border border-amber-500/40 text-[11px] font-mono text-amber-200 whitespace-nowrap backdrop-blur-md shadow-lg flex items-center gap-1.5">
                    <span className="font-semibold">Rahul</span>
                    <span className="text-[10px] text-amber-400/80">1 min behind</span>
                  </div>
                </div>
              </div>

              {/* Member 2: Keshav */}
              <div 
                className="absolute transition-all duration-700 ease-out"
                style={{ left: `${30 + (progress * 0.5)}%`, top: `${58 - (progress * 0.3)}%` }}
              >
                <div className="relative flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.9)]" />
                  <div className="px-2.5 py-1 rounded-md bg-[#0A0D14]/90 border border-white/15 text-[11px] font-mono text-white/90 whitespace-nowrap backdrop-blur-md shadow-lg flex items-center gap-1.5">
                    <span className="font-semibold">Keshav</span>
                    <span className="text-[10px] text-white/50">Moving</span>
                  </div>
                </div>
              </div>

              {/* Member 3: Aditi */}
              <div 
                className="absolute transition-all duration-700 ease-out"
                style={{ left: `${42 + (progress * 0.48)}%`, top: `${48 - (progress * 0.32)}%` }}
              >
                <div className="relative flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.9)]" />
                  <div className="px-2.5 py-1 rounded-md bg-[#0A0D14]/90 border border-white/15 text-[11px] font-mono text-white/90 whitespace-nowrap backdrop-blur-md shadow-lg flex items-center gap-1.5">
                    <span className="font-semibold">Aditi</span>
                    <span className="text-[10px] text-white/50">Moving</span>
                  </div>
                </div>
              </div>

              {/* Member 4: YOU (Spotlight Anchor Marker) */}
              <div 
                className="absolute transition-all duration-700 ease-out z-30"
                style={{ left: `${56 + (progress * 0.42)}%`, top: `${38 - (progress * 0.32)}%` }}
              >
                <div className="relative flex flex-col items-center">
                  <div className="relative flex items-center justify-center">
                    <span className="absolute w-10 h-10 rounded-full border border-white/50 animate-ping" />
                    <span className="absolute w-7 h-7 rounded-full bg-white/20 blur-sm" />
                    <div className="w-4 h-4 rounded-full bg-white border-2 border-cyan-400 shadow-[0_0_20px_rgba(255,255,255,1)] flex items-center justify-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-black" />
                    </div>
                  </div>
                  <div className="mt-1 px-2.5 py-0.5 rounded bg-white text-black font-mono text-[10px] font-bold uppercase tracking-wider shadow-2xl border border-white">
                    YOU
                  </div>
                </div>
              </div>

              {/* Member 5: Priya */}
              <div 
                className="absolute transition-all duration-700 ease-out"
                style={{ left: `${68 + (progress * 0.38)}%`, top: `${26 - (progress * 0.28)}%` }}
              >
                <div className="relative flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.9)]" />
                  <div className="px-2.5 py-1 rounded-md bg-[#0A0D14]/90 border border-white/15 text-[11px] font-mono text-white/90 whitespace-nowrap backdrop-blur-md shadow-lg flex items-center gap-1.5">
                    <span className="font-semibold">Priya</span>
                    <span className="text-[10px] text-white/50">Moving</span>
                  </div>
                </div>
              </div>

            </div>

            {/* Bottom-Left Trip Readout Overlay */}
            <div className="absolute bottom-4 left-4 z-20">
              <div className="p-3.5 rounded-xl bg-[#080A0F]/90 border border-white/10 backdrop-blur-xl font-mono text-left max-w-xs shadow-2xl">
                <div className="text-[10px] tracking-widest text-white/50 uppercase font-semibold">
                  TRIP STREAM
                </div>
                <div className="text-sm font-bold text-white tracking-wide mt-0.5">
                  Manali → Solang Valley
                </div>
                <div className="text-[11px] text-white/60 mt-1">
                  Remaining: <span className="text-white font-medium">{remainingDist}km</span> &nbsp;•&nbsp; Speed: <span className="text-emerald-400 font-medium">{currentSpeed} km/h</span>
                </div>
              </div>
            </div>

            {/* Bottom-Right Context Readout */}
            <div className="absolute bottom-4 right-4 z-20">
              <div className="px-3.5 py-2 rounded-xl bg-[#080A0F]/90 border border-white/10 backdrop-blur-xl font-mono text-xs text-white/70 flex items-center gap-2 shadow-2xl">
                <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
                <span>REAL-TIME STREAMING</span>
              </div>
            </div>

          </div>

          {/* Simulation Scrubber Controls Bar */}
          <div className="px-6 py-3.5 bg-[#080809] border-t border-white/10 flex flex-wrap items-center justify-between gap-4 font-mono text-xs text-white/60">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 border border-white/15 flex items-center justify-center text-white transition-colors"
                title={isPlaying ? "Pause Simulation" : "Play Simulation"}
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
              </button>
              <button
                onClick={() => setProgress(0)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-white/70 hover:text-white transition-colors"
                title="Reset Simulation"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <span className="text-[11px] text-white/40">
                MOVEMENT REPLAY
              </span>
            </div>

            {/* Trip Scrubber Bar */}
            <div className="flex-1 max-w-md flex items-center gap-3">
              <span className="text-[10px] text-white/40">START</span>
              <input
                type="range"
                min="0"
                max="100"
                value={progress}
                onChange={(e) => setProgress(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-white"
              />
              <span className="text-[10px] text-white/40">DEST</span>
            </div>
          </div>

        </div>
      </section>

      {/* 3. EDITORIAL TELEMETRY STRIP (Single Horizontal Visual Section) */}
      <section className="px-6 max-w-5xl mx-auto mb-36">
        <div className="border-t border-b border-white/10 py-16 space-y-12">
          
          <div className="max-w-2xl space-y-3">
            <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
              LIVE TELEMETRY
            </div>
            <h2 className="text-2xl sm:text-4xl font-medium text-white tracking-tight leading-tight">
              EVERY POSITION TELLS PART OF THE STORY.
            </h2>
            <p className="text-xs sm:text-base text-white/60 font-normal leading-relaxed">
              RALLY keeps each member's position, movement, and route context together so the group can understand where everyone is without constantly checking in.
            </p>
          </div>

          {/* Horizontal Telemetry Live Readouts */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 font-mono text-xs">
            
            {/* Speed Readout */}
            <div className="space-y-2">
              <div className="flex justify-between text-white/70">
                <span className="uppercase text-white/40">SPEED</span>
                <span className="text-white font-bold">{currentSpeed} km/h</span>
              </div>
              <div className="relative w-full h-[2px] bg-white/15 rounded-full overflow-hidden">
                <div 
                  className="absolute top-0 bottom-0 bg-cyan-400 transition-all duration-300"
                  style={{ width: `${(currentSpeed / 90) * 100}%` }}
                />
              </div>
            </div>

            {/* Heading Readout */}
            <div className="space-y-2">
              <div className="flex justify-between text-white/70">
                <span className="uppercase text-white/40">HEADING</span>
                <span className="text-white font-bold">{currentHdg}° NW</span>
              </div>
              <div className="relative w-full h-[2px] bg-white/15 rounded-full overflow-hidden">
                <div 
                  className="absolute top-0 bottom-0 bg-white transition-all duration-300"
                  style={{ width: `${(currentHdg / 360) * 100}%` }}
                />
              </div>
            </div>

            {/* Elevation Readout */}
            <div className="space-y-2">
              <div className="flex justify-between text-white/70">
                <span className="uppercase text-white/40">ELEVATION</span>
                <span className="text-white font-bold">{currentAlt.toLocaleString()} m</span>
              </div>
              <div className="relative w-full h-[2px] bg-white/15 rounded-full overflow-hidden">
                <div 
                  className="absolute top-0 bottom-0 bg-emerald-400 transition-all duration-300"
                  style={{ width: `${((currentAlt - 2000) / 1000) * 100}%` }}
                />
              </div>
            </div>

            {/* Distance Readout */}
            <div className="space-y-2">
              <div className="flex justify-between text-white/70">
                <span className="uppercase text-white/40">DISTANCE REMAINING</span>
                <span className="text-white font-bold">{remainingDist} km</span>
              </div>
              <div className="relative w-full h-[2px] bg-white/15 rounded-full overflow-hidden">
                <div 
                  className="absolute top-0 bottom-0 bg-white transition-all duration-300"
                  style={{ width: `${100 - progress}%` }}
                />
              </div>
            </div>

          </div>

        </div>
      </section>

      {/* 4. ASYMMETRIC EDITORIAL STATEMENT */}
      <section className="px-6 max-w-5xl mx-auto mb-36">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-8 sm:gap-12">
          
          <div className="w-full md:w-1/2 space-y-4">
            <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
              NO FRICTION COMMUNICATION
            </div>
            <h2 className="text-3xl sm:text-5xl font-medium tracking-tight text-white leading-[1.08]">
              NO MORE <br />
              <span className="font-serif italic font-normal text-white/85">
                "WHERE ARE YOU?"
              </span>
            </h2>
          </div>

          <div className="w-full md:w-1/2 pt-2 md:pt-10">
            <p className="text-sm sm:text-lg text-white/70 font-normal leading-relaxed">
              Everyone's position is already there — on the same map, on the same trip. No radio chatter, no text messages while driving, no constant pulling over to check in.
            </p>
          </div>

        </div>
      </section>

      {/* 5. TRIP TIMELINE (SEE THE TRIP AS IT HAPPENS) */}
      <section className="px-6 max-w-5xl mx-auto mb-36">
        <div className="border-t border-white/10 pt-16 space-y-12">
          
          <div className="max-w-2xl space-y-3">
            <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
              MOVEMENT LIFECYCLE
            </div>
            <h2 className="text-2xl sm:text-4xl font-medium text-white tracking-tight">
              SEE THE TRIP AS IT HAPPENS.
            </h2>
          </div>

          {/* Interactive Visual Connected Timeline */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-6 relative">
            
            {/* Horizontal Connecting Line on Desktop */}
            <div className="hidden md:block absolute top-[18px] left-6 right-6 h-[1px] bg-white/15 z-0" />

            {TIMELINE_STAGES.map((stage, idx) => {
              const isSelected = activeStage === idx;
              return (
                <div 
                  key={stage.num}
                  onClick={() => setActiveStage(idx)}
                  className="relative z-10 cursor-pointer group space-y-3"
                >
                  <div className="flex items-center gap-3 md:block">
                    {/* Number Node */}
                    <div className={`w-9 h-9 rounded-full border font-mono text-xs flex items-center justify-center transition-all ${
                      isSelected 
                        ? 'bg-white text-black font-bold border-white shadow-[0_0_15px_rgba(255,255,255,0.4)]' 
                        : 'bg-[#000000] text-white/40 border-white/20 group-hover:border-white/60 group-hover:text-white'
                    }`}>
                      {stage.num}
                    </div>

                    <div className="font-mono text-xs font-bold text-white tracking-wider uppercase md:mt-3">
                      {stage.label}
                    </div>
                  </div>

                  <p className="text-xs text-white/60 font-normal leading-relaxed pl-12 md:pl-0">
                    {stage.desc}
                  </p>
                </div>
              );
            })}

          </div>

        </div>
      </section>

      {/* 6. GROUP MOVEMENT SECTION (TOGETHER, WITHOUT BEING TOGETHER) */}
      <section className="px-6 max-w-5xl mx-auto mb-36">
        <div className="border-t border-white/10 pt-16 grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          
          <div className="space-y-4">
            <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
              INDIVIDUAL AUTONOMY
            </div>
            <h2 className="text-3xl sm:text-5xl font-medium tracking-tight text-white leading-[1.08]">
              TOGETHER, <br />
              <span className="font-serif italic font-normal text-white/85">
                WITHOUT BEING TOGETHER.
              </span>
            </h2>
            <p className="text-xs sm:text-base text-white/60 font-normal leading-relaxed pt-2">
              Everyone can move at their own pace while the group still has one shared picture of the trip. Stop for fuel, take a detour, or catch up later without losing connection.
            </p>
          </div>

          {/* Lightweight SVG Visualizing Group Convergence */}
          <div className="p-8 rounded-2xl bg-[#030304] border border-white/10 font-mono text-xs flex items-center justify-center">
            <svg className="w-full max-w-xs h-44" viewBox="0 0 300 160">
              {/* Converging route lines */}
              <path d="M 30 30 Q 150 40 270 80" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2" strokeDasharray="4 4" />
              <path d="M 30 80 Q 150 80 270 80" fill="none" stroke="#22d3ee" strokeWidth="2.5" />
              <path d="M 30 130 Q 150 120 270 80" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2" strokeDasharray="4 4" />

              {/* Member Nodes */}
              <circle cx="30" cy="30" r="5" fill="#38bdf8" />
              <text x="30" y="18" fill="rgba(255,255,255,0.5)" textAnchor="middle" fontSize="10">MEMBER A</text>

              <circle cx="30" cy="80" r="5" fill="#ffffff" />
              <text x="30" y="68" fill="rgba(255,255,255,0.9)" textAnchor="middle" fontSize="10">YOU</text>

              <circle cx="30" cy="130" r="5" fill="#34d399" />
              <text x="30" y="150" fill="rgba(255,255,255,0.5)" textAnchor="middle" fontSize="10">MEMBER B</text>

              {/* Converged Group Node */}
              <circle cx="270" cy="80" r="7" fill="#22d3ee" className="animate-pulse" />
              <text x="270" y="105" fill="#22d3ee" textAnchor="middle" fontSize="10" fontWeight="bold">DESTINATION</text>
            </svg>
          </div>

        </div>
      </section>

      {/* 7. PLANNED VS REAL MOVEMENT */}
      <section className="px-6 max-w-5xl mx-auto mb-36">
        <div className="border-t border-white/10 pt-16 grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          
          <div className="space-y-4">
            <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
              PATH RECONSTRUCTION
            </div>
            <h2 className="text-2xl sm:text-4xl font-medium tracking-tight text-white leading-tight">
              PLANNED ROUTE. <br />
              <span className="font-serif italic font-normal text-white/85">
                REAL MOVEMENT.
              </span>
            </h2>
            <p className="text-xs sm:text-base text-white/60 font-normal leading-relaxed">
              RALLY doesn't just show where the route was supposed to go. It preserves and reconstructs the actual journey that happened along the way.
            </p>
          </div>

          {/* Compact Vector Comparison SVG */}
          <div className="p-8 rounded-2xl bg-[#030304] border border-white/10 font-mono text-xs space-y-6">
            <div className="space-y-2">
              <div className="text-[10px] text-white/40 uppercase tracking-wider">PLANNED INTENT</div>
              <div className="flex items-center gap-3 text-white/60">
                <span className="text-white font-bold">START</span>
                <div className="flex-1 h-[2px] bg-white/20 relative">
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-white/40" />
                </div>
                <span>DEST</span>
              </div>
            </div>

            <div className="space-y-2 pt-2 border-t border-white/10">
              <div className="text-[10px] text-emerald-400 uppercase tracking-wider font-bold">ACTUAL JOURNEY</div>
              <div className="flex items-center gap-3 text-white">
                <span className="text-white font-bold">START</span>
                <div className="flex-1 h-[2px] bg-gradient-to-r from-cyan-400 via-emerald-400 to-white relative">
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                </div>
                <span className="text-emerald-400 font-bold">ARRIVED</span>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* 8. FINAL EDITORIAL CTA */}
      <section className="pb-32 px-6 max-w-4xl mx-auto text-center border-t border-white/10 pt-24">
        <h2 className="text-3xl sm:text-5xl md:text-6xl font-medium text-white tracking-tight leading-tight">
          KEEP <br />
          THE WHOLE GROUP <br />
          <span className="font-serif italic font-normal text-white/90">
            IN VIEW.
          </span>
        </h2>

        <p className="mt-6 text-sm sm:text-lg text-white/60 font-normal font-sans max-w-md mx-auto">
          One shared map. One trip. Everyone moving together.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-4 font-mono text-xs">
          <Link
            href="/create-group"
            className="px-7 py-3.5 min-h-[44px] rounded-full bg-white text-black font-semibold tracking-wider uppercase hover:bg-white/90 transition-all duration-200 shadow-[0_0_30px_rgba(255,255,255,0.2)] hover:scale-[1.02] flex items-center"
          >
            START A RALLY
          </Link>
          <Link
            href="/demo"
            className="px-7 py-3.5 min-h-[44px] rounded-full bg-white/[0.04] border border-white/20 text-white font-semibold tracking-wider uppercase hover:bg-white/[0.08] hover:border-white/40 transition-all duration-200 flex items-center"
          >
            EXPLORE RALLY
          </Link>
        </div>
      </section>

      {/* Footer */}
      <Footer />
    </div>
  );
}
