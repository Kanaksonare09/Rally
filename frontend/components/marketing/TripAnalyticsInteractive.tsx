'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Clock, 
  MapPin, 
  Activity, 
  FileClock, 
  CheckCircle2, 
  ChevronRight,
  ArrowRight
} from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

interface TripEvent {
  timeStr: string;
  progress: number;
  title: string;
  desc: string;
  type: 'start' | 'stop' | 'deviation' | 'regroup' | 'destination';
}

const TRIP_EVENTS: TripEvent[] = [
  { timeStr: '12:42', progress: 0, title: 'GROUP STARTED', desc: 'Departure from Manali Base', type: 'start' },
  { timeStr: '13:10', progress: 0.28, title: 'MEMBER STOPPED', desc: 'Chichoga Cafe Rest (8m duration)', type: 'stop' },
  { timeStr: '13:45', progress: 0.52, title: 'ROUTE DEVIATION', desc: 'Solang Ridge Trail split (+85m lag)', type: 'deviation' },
  { timeStr: '14:20', progress: 0.76, title: 'GROUP REGROUPED', desc: 'Palu Checkpoint (All 5 connected)', type: 'regroup' },
  { timeStr: '15:18', progress: 1.0, title: 'DESTINATION REACHED', desc: 'Solang Valley Plateau', type: 'destination' },
];

const TRIP_HISTORY = [
  { date: 'AUG 24', title: 'Manali → Solang Valley', status: 'Completed', distance: '42.7 km', duration: '2h 36m' },
  { date: 'AUG 18', title: 'Delhi → Jaipur Highway', status: 'Completed', distance: '268.4 km', duration: '4h 12m' },
  { date: 'AUG 11', title: 'Kasol Pin Parvati Loop', status: 'Cancelled', distance: '14.2 km', duration: '1h 05m' },
];

export default function TripAnalyticsInteractive() {
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [progress, setProgress] = useState<number>(0.42); // 0 to 1
  const [selectedArchiveIndex, setSelectedArchiveIndex] = useState<number>(0);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameId = useRef<number | null>(null);
  const mousePos = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });

  // Handle Mouse movement for subtle 60fps parallax effect (inertia damped)
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (typeof window === 'undefined' || window.innerWidth < 768) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2);
    const y = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2);
    mousePos.current.targetX = x * 16;
    mousePos.current.targetY = y * 10;
  }, []);

  // Playback timer
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setProgress((prev) => (prev >= 1 ? 0 : prev + 0.003));
    }, 50);
    return () => clearInterval(interval);
  }, [isPlaying]);

  // Main Canvas Render Loop (60fps requestAnimationFrame)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = (canvas.width = canvas.parentElement?.clientWidth || 900);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 450);

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener('resize', handleResize);

    const getRoutePoint = (t: number) => {
      const x = width * 0.1 + t * width * 0.8;
      const y = height * 0.65 - Math.sin(t * Math.PI * 1.4) * height * 0.4;
      return { x, y };
    };

    const render = () => {
      // Damped parallax mouse interpolation
      mousePos.current.x += (mousePos.current.targetX - mousePos.current.x) * 0.05;
      mousePos.current.y += (mousePos.current.targetY - mousePos.current.y) * 0.05;
      const ox = mousePos.current.x;
      const oy = mousePos.current.y;

      ctx.clearRect(0, 0, width, height);

      // 1. Technical Cartography Grid Lines
      ctx.save();
      ctx.translate(ox * 0.3, oy * 0.3);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
      ctx.lineWidth = 1;
      const step = 48;
      for (let x = 0; x < width; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      ctx.restore();

      // 2. Full Faint Recorded Route Line
      ctx.save();
      ctx.translate(ox * 0.6, oy * 0.6);
      ctx.beginPath();
      for (let t = 0; t <= 1; t += 0.01) {
        const pt = getRoutePoint(t);
        if (t === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 6]);
      ctx.stroke();
      ctx.setLineDash([]);

      // 3. Progressive Replayed Route Solid Path
      ctx.beginPath();
      const maxT = Math.min(1, Math.max(0, progress));
      for (let t = 0; t <= maxT; t += 0.005) {
        const pt = getRoutePoint(t);
        if (t === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 3;
      ctx.stroke();

      // 4. Draw Event Markers on Route
      TRIP_EVENTS.forEach((ev) => {
        if (ev.progress <= maxT) {
          const pt = getRoutePoint(ev.progress);
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
          ctx.fillStyle = ev.type === 'deviation' ? '#f59e0b' : '#FFFFFF';
          ctx.fill();

          ctx.font = '10px monospace';
          ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
          ctx.fillText(ev.title, pt.x + 8, pt.y - 8);
        }
      });

      // 5. Active Node Head Marker
      const currentPt = getRoutePoint(maxT);
      ctx.beginPath();
      ctx.arc(currentPt.x, currentPt.y, 9 + Math.sin(Date.now() / 150) * 2, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(currentPt.x, currentPt.y, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = '#FFFFFF';
      ctx.fill();

      ctx.restore();

      animFrameId.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animFrameId.current) cancelAnimationFrame(animFrameId.current);
      window.removeEventListener('resize', handleResize);
    };
  }, [progress]);

  // Derived dynamic metrics connected to replay progress
  const currentDistance = (progress * 42.7).toFixed(1);
  const currentMinutesTotal = Math.floor(progress * 156);
  const durHours = Math.floor(currentMinutesTotal / 60);
  const durMins = currentMinutesTotal % 60;
  const currentTopSpeed = Math.round(20 + Math.sin(progress * Math.PI * 2.5) * 27);
  const currentStopsCount = progress > 0.76 ? 6 : progress > 0.28 ? 3 : 1;

  return (
    <div className="bg-[#000000] text-white min-h-screen font-sans selection:bg-white/20 selection:text-white">
      {/* Global Header */}
      <Navbar />

      {/* 2. HERO SECTION */}
      <section className="pt-16 pb-6 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono tracking-[0.2em] text-white/70 uppercase mb-6"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
          TRIP ANALYTICS
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl md:text-7xl font-medium tracking-tight text-white max-w-3xl leading-[1.08]"
        >
          Every trip <br />
          <span className="font-serif italic font-normal text-white/90 tracking-normal">
            leaves a record.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-6 text-base sm:text-lg text-white/60 max-w-2xl font-normal leading-relaxed"
        >
          Trips aren't deleted when they end — they become history you can review, replay, and learn from.
        </motion.p>
      </section>

      {/* 3 & 4 & 5 & 6. MAIN TRIP RECORD VISUALIZATION (Header + Replay Canvas + Timeline + Data Line) */}
      <section className="px-4 sm:px-6 max-w-6xl mx-auto my-6">
        
        {/* Header Metadata Banner (Matches Item #3) */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4 font-mono text-xs text-white/60 border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 rounded bg-white/10 font-bold text-white">TRIP 014</span>
            <span className="text-white font-semibold">MANALI → SOLANG VALLEY</span>
          </div>

          <div className="flex items-center gap-4 text-[11px] text-white/40">
            <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold uppercase">COMPLETED</span>
            <span>TIMEFRAME: 12:42 — 15:18</span>
          </div>
        </div>

        {/* Spatial Route Cartography Canvas Surface */}
        <div 
          onMouseMove={handleMouseMove}
          className="relative w-full h-[440px] sm:h-[500px] rounded-[24px] bg-[#030303] border border-white/10 overflow-hidden shadow-[0_30px_90px_rgba(0,0,0,0.95)] flex flex-col justify-between p-6 select-none"
        >
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
          />

          {/* Top Info Bar */}
          <div className="relative z-20 flex justify-between items-start font-mono text-xs">
            <div className="text-white/50 text-[11px]">
              RECORDED JOURNEY REPLAY (HISTORICAL ARCHIVE)
            </div>
            <div className="text-white/40 text-[11px]">
              REPLAY RECONSTRUCTION: 100%
            </div>
          </div>

          {/* Bottom Replay Control Bar */}
          <div className="relative z-20 bg-[#08080A]/90 border border-white/10 backdrop-blur-md rounded-xl p-4 space-y-3 font-mono text-xs">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 border border-white/15 flex items-center justify-center text-white transition-colors shrink-0"
                title={isPlaying ? "Pause Replay" : "Play Replay"}
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
              </button>

              <div className="flex-1 flex items-center gap-3">
                <span className="text-[11px] text-white/50">12:42</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.001"
                  value={progress}
                  onChange={(e) => setProgress(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-white/15 rounded-lg appearance-none cursor-pointer accent-white"
                />
                <span className="text-[11px] text-white/50">15:18</span>
              </div>

              <button
                onClick={() => setProgress(0)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-white/70 hover:text-white transition-colors shrink-0"
                title="Reset Replay"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

        </div>

        {/* 7. TRIP METRICS (Editorial Horizontal Data Line, NOT 4 Cards) */}
        <div className="mt-6 p-6 rounded-2xl bg-[#030303] border border-white/10 font-mono">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 text-center sm:text-left divide-y sm:divide-y-0 sm:divide-x divide-white/10">
            <div className="pt-2 sm:pt-0 sm:pr-4">
              <div className="text-3xl sm:text-4xl font-light text-white leading-none">
                {currentDistance} <span className="text-xs text-white/40">km</span>
              </div>
              <div className="text-[10px] text-white/40 uppercase tracking-widest mt-1">DISTANCE</div>
            </div>

            <div className="pt-2 sm:pt-0 sm:px-4">
              <div className="text-3xl sm:text-4xl font-light text-white leading-none">
                {durHours}h {durMins}m
              </div>
              <div className="text-[10px] text-white/40 uppercase tracking-widest mt-1">DURATION</div>
            </div>

            <div className="pt-2 sm:pt-0 sm:px-4">
              <div className="text-3xl sm:text-4xl font-light text-white leading-none">
                {currentTopSpeed} <span className="text-xs text-white/40">km/h</span>
              </div>
              <div className="text-[10px] text-white/40 uppercase tracking-widest mt-1">TOP SPEED</div>
            </div>

            <div className="pt-2 sm:pt-0 sm:pl-4">
              <div className="text-3xl sm:text-4xl font-light text-white leading-none">
                {currentStopsCount}
              </div>
              <div className="text-[10px] text-white/40 uppercase tracking-widest mt-1">STOPS RECORDED</div>
            </div>
          </div>
        </div>

        {/* 8. SYNCHRONIZED TRIP EVENTS STREAM LIST (Matches Item #8) */}
        <div className="mt-8 font-mono text-xs">
          <div className="text-[10px] text-white/40 uppercase tracking-widest mb-3">
            SYNCHRONIZED EVENT STREAM (CLICK EVENT TO JUMP)
          </div>

          <div className="space-y-2">
            {TRIP_EVENTS.map((ev) => {
              const isPassed = progress >= ev.progress;
              const isCurrent = Math.abs(progress - ev.progress) < 0.08;
              return (
                <button
                  key={ev.title}
                  onClick={() => {
                    setProgress(ev.progress);
                    setIsPlaying(false);
                  }}
                  className={`w-full p-4 rounded-xl border text-left transition-all duration-200 flex items-center justify-between ${
                    isCurrent
                      ? 'bg-white/10 border-white text-white shadow-lg'
                      : isPassed
                      ? 'bg-white/[0.03] border-white/10 text-white/80'
                      : 'bg-white/[0.01] border-white/5 text-white/40 hover:border-white/15'
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <span className="text-white/40 font-bold">{ev.timeStr}</span>
                    <div>
                      <div className="font-bold tracking-wider text-xs text-white">{ev.title}</div>
                      <div className="text-[10px] text-white/50">{ev.desc}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-[10px]">
                    {ev.type === 'deviation' && <span className="text-amber-400 font-semibold">DEVIATION</span>}
                    {ev.type === 'destination' && <span className="text-emerald-400 font-semibold">DESTINATION</span>}
                    <ChevronRight className="w-3.5 h-3.5 text-white/30" />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

      </section>

      {/* 9 & 11. "REVIEW WHAT HAPPENED" NARRATIVE & TRIP RHYTHM TRACE */}
      <section className="py-24 px-6 max-w-5xl mx-auto border-t border-white/5">
        <div className="max-w-3xl">
          <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">
            HISTORICAL INTELLIGENCE
          </div>

          <h2 className="text-3xl sm:text-5xl font-medium tracking-tight text-white leading-tight">
            Review what happened, <br />
            <span className="font-serif italic font-normal text-white/85">
              not just what was planned.
            </span>
          </h2>

          <p className="mt-6 text-base sm:text-lg text-white/60 font-normal leading-relaxed">
            Completed and cancelled trips stay in your group's history, exactly as they happened.
          </p>
        </div>

        {/* 11. Trip Rhythm Visualization (Continuous Horizontal Movement Trace) */}
        <div className="mt-12 p-8 rounded-[24px] bg-[#030303] border border-white/10 font-mono">
          <div className="text-xs text-white/50 mb-6 flex justify-between">
            <span>CONTINUOUS TRIP PACE RHYTHM TRACE</span>
            <span className="text-white/40">12:42 ─── 15:18</span>
          </div>

          <div className="h-32 w-full relative flex items-center justify-center">
            <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 600 100">
              <path
                d="M 0 50 Q 60 20, 120 50 T 200 85 T 320 20 T 450 70 T 600 50"
                fill="none"
                stroke="#FFFFFF"
                strokeWidth="2"
              />
              <circle cx="120" cy="50" r="4" fill="#38bdf8" />
              <text x="100" y="30" fill="rgba(255,255,255,0.6)" fontSize="9" fontFamily="monospace">MOVING (45 km/h)</text>

              <circle cx="200" cy="85" r="4" fill="#ef4444" />
              <text x="180" y="98" fill="#ef4444" fontSize="9" fontFamily="monospace">STOPPED (8m)</text>

              <circle cx="320" cy="20" r="4" fill="#f59e0b" />
              <text x="300" y="12" fill="#f59e0b" fontSize="9" fontFamily="monospace">DEVIATING (+85m)</text>

              <circle cx="450" cy="70" r="4" fill="#34d399" />
              <text x="430" y="85" fill="#34d399" fontSize="9" fontFamily="monospace">REGROUPED</text>
            </svg>
          </div>
        </div>
      </section>

      {/* 12. HISTORY ARCHIVE TIMELINE */}
      <section className="py-20 px-6 max-w-5xl mx-auto border-t border-white/5 font-mono text-xs">
        <div className="text-[10px] text-white/40 uppercase tracking-widest mb-6">
          GROUP TRIP ARCHIVE HISTORY
        </div>

        <div className="space-y-3">
          {TRIP_HISTORY.map((trip, idx) => (
            <div
              key={trip.date}
              onClick={() => setSelectedArchiveIndex(idx)}
              className={`p-6 rounded-2xl border transition-all duration-200 cursor-pointer flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${
                selectedArchiveIndex === idx
                  ? 'bg-white/10 border-white text-white'
                  : 'bg-white/[0.02] border-white/10 text-white/70 hover:border-white/20 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-4">
                <span className="text-white/40 font-bold">{trip.date}</span>
                <div>
                  <div className="font-bold text-sm text-white">{trip.title}</div>
                  <div className="text-[10px] text-white/50">{trip.distance} • {trip.duration}</div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                  trip.status === 'Completed' ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400' : 'bg-red-500/10 border border-red-500/30 text-red-400'
                }`}>
                  {trip.status}
                </span>
                <ChevronRight className="w-4 h-4 text-white/30" />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 13 & 14. PERMANENT RECORD & DATA CONVERGENCE STORY */}
      <section className="py-24 px-6 max-w-4xl mx-auto text-center border-t border-white/5">
        <h2 className="text-3xl sm:text-5xl md:text-6xl font-medium tracking-tight text-white leading-tight">
          The trip ends. <br />
          <span className="font-serif italic font-normal text-white/85">
            The record doesn't.
          </span>
        </h2>

        <p className="mt-6 text-base sm:text-lg text-white/60 max-w-xl mx-auto font-normal leading-relaxed">
          Every completed or cancelled trip remains available as part of the group's history.
        </p>

        {/* Data Convergence Diagram */}
        <div className="mt-16 max-w-3xl mx-auto font-mono text-xs">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-white/70">
            <span className="font-bold tracking-widest text-white uppercase">TIME</span>
            <span className="text-white/30">+</span>
            <span className="font-bold tracking-widest text-white uppercase">POSITION</span>
            <span className="text-white/30">+</span>
            <span className="font-bold tracking-widest text-white uppercase">SPEED</span>
            <span className="text-white/30">+</span>
            <span className="font-bold tracking-widest text-white uppercase">EVENTS</span>
            <span className="text-white/30">=</span>
            <div className="p-3 rounded-xl bg-white/10 border border-white/20">
              <span className="font-bold tracking-widest text-white uppercase">TRIP RECORD</span>
            </div>
          </div>
        </div>
      </section>

      {/* 15. MINIMAL FINAL CTA */}
      <section className="pb-28 px-6 max-w-3xl mx-auto text-center">
        <div className="pt-16 border-t border-white/10 flex flex-col items-center">
          <h3 className="text-3xl sm:text-5xl font-medium text-white tracking-tight">
            See the whole journey.
          </h3>

          <p className="mt-4 text-base text-white/60 font-normal font-sans">
            Replay the route. Understand what happened. Keep the record.
          </p>

          <div className="mt-8">
            <Link
              href="/register"
              className="px-8 py-4 rounded-full bg-white text-black text-xs font-mono font-semibold tracking-wider uppercase hover:bg-white/90 transition-all duration-200 shadow-[0_0_30px_rgba(255,255,255,0.2)] hover:scale-[1.02] inline-block"
            >
              Start a Rally
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <Footer />
    </div>
  );
}
