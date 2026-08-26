'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Navigation, 
  Compass, 
  Gauge, 
  MapPin, 
  GitBranch, 
  Layers, 
  Activity, 
  ChevronRight 
} from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

type ViewMode = 'planned' | 'actual' | 'both';

interface TimelineEvent {
  timeStr: string;
  progress: number;
  label: string;
  desc: string;
  speed: number;
  lat: number;
  lng: number;
  heading: number;
}

const TIMELINE_EVENTS: TimelineEvent[] = [
  { timeStr: '00:00', progress: 0, label: 'START', desc: 'Departure from Manali Base', speed: 12, lat: 32.2431, lng: 77.1892, heading: 45 },
  { timeStr: '14:20', progress: 0.32, label: 'DEVIATION', desc: 'Solang Ridge Trail split', speed: 48, lat: 32.2612, lng: 77.1750, heading: 128 },
  { timeStr: '22:45', progress: 0.54, label: 'STEEP ASCENT', desc: 'Elevation +420m, speed reduced', speed: 24, lat: 32.2780, lng: 77.1630, heading: 340 },
  { timeStr: '31:10', progress: 0.76, label: 'REGROUP', desc: 'Palu Checkpoint rest stop', speed: 0, lat: 32.2920, lng: 77.1540, heading: 320 },
  { timeStr: '42:18', progress: 1.0, label: 'DESTINATION', desc: 'Solang Valley Plateau', speed: 35, lat: 32.3080, lng: 77.1480, heading: 310 },
];

export default function RouteIntelligenceInteractive() {
  const [viewMode, setViewMode] = useState<ViewMode>('both');
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [progress, setProgress] = useState<number>(0.35); // 0 to 1
  const [reconstructStage, setReconstructStage] = useState<'points' | 'connected' | 'journey' | 'understood'>('understood');
  const [activeStatementHover, setActiveStatementHover] = useState<number | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameId = useRef<number | null>(null);
  const mousePos = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });

  // Handle Mouse movement for subtle 60fps parallax effect (inertia damped)
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (typeof window === 'undefined' || window.innerWidth < 768) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2);
    const y = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2);
    mousePos.current.targetX = x * 18;
    mousePos.current.targetY = y * 12;
  }, []);

  // Continuous animation loop for progress scrubber
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
    let height = (canvas.height = canvas.parentElement?.clientHeight || 500);

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener('resize', handleResize);

    // Parametric spline for Planned Route
    const getPlannedPoint = (t: number) => {
      const x = width * 0.12 + t * width * 0.76;
      const y = height * 0.75 - Math.sin(t * Math.PI * 1.3) * height * 0.45;
      return { x, y };
    };

    // Parametric spline for Actual Route (diverges in middle section)
    const getActualPoint = (t: number) => {
      const base = getPlannedPoint(t);
      // Divergence bulge around t=0.3 to 0.6
      let devX = 0;
      let devY = 0;
      if (t > 0.25 && t < 0.7) {
        const factor = Math.sin(((t - 0.25) / 0.45) * Math.PI);
        devY = -factor * (height * 0.22);
        devX = factor * (width * 0.06);
      }
      return { x: base.x + devX, y: base.y + devY };
    };

    const render = () => {
      // Damped parallax mouse interpolation
      mousePos.current.x += (mousePos.current.targetX - mousePos.current.x) * 0.05;
      mousePos.current.y += (mousePos.current.targetY - mousePos.current.y) * 0.05;
      const ox = mousePos.current.x;
      const oy = mousePos.current.y;

      ctx.clearRect(0, 0, width, height);

      // 1. Draw Subtle Technical Cartography Grid & Scales
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

      // Compass Rose Watermark
      ctx.font = '10px monospace';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.fillText('N 32°14\'31"  E 77°11\'20"', 24, 30);
      ctx.fillText('SCALE: 1:25,000 (SOLANG PASS)', width - 200, 30);
      ctx.restore();

      // 2. Draw PLANNED ROUTE Line (faint dashed)
      if (viewMode === 'planned' || viewMode === 'both') {
        ctx.save();
        ctx.translate(ox * 0.5, oy * 0.5);
        ctx.beginPath();
        for (let t = 0; t <= 1; t += 0.01) {
          const pt = getPlannedPoint(t);
          if (t === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.22)';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 6]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
      }

      // 3. Draw ACTUAL ROUTE Line (progressive bright white path + recorded points)
      if (viewMode === 'actual' || viewMode === 'both') {
        ctx.save();
        ctx.translate(ox * 0.7, oy * 0.7);

        // Draw full faint actual path behind
        ctx.beginPath();
        for (let t = 0; t <= 1; t += 0.01) {
          const pt = getActualPoint(t);
          if (t === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Draw progressive solid actual path up to current progress
        ctx.beginPath();
        const maxT = Math.min(1, Math.max(0, progress));
        for (let t = 0; t <= maxT; t += 0.005) {
          const pt = getActualPoint(t);
          if (t === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        }
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 3;
        ctx.stroke();

        // Draw individual recorded GPS points along actual path
        const totalPoints = 35;
        for (let i = 0; i <= totalPoints; i++) {
          const ptT = i / totalPoints;
          if (ptT > maxT) break;
          const pt = getActualPoint(ptT);

          // Point dot
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 2.5, 0, Math.PI * 2);
          ctx.fillStyle = '#FFFFFF';
          ctx.fill();

          // Small directional arrow on every 5th point
          if (i % 5 === 0 && ptT > 0) {
            const prevPt = getActualPoint(Math.max(0, ptT - 0.02));
            const angle = Math.atan2(pt.y - prevPt.y, pt.x - prevPt.x);
            
            ctx.save();
            ctx.translate(pt.x, pt.y);
            ctx.rotate(angle);
            ctx.beginPath();
            ctx.moveTo(6, 0);
            ctx.lineTo(-3, -3);
            ctx.lineTo(-3, 3);
            ctx.closePath();
            ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
            ctx.fill();
            ctx.restore();
          }
        }

        // Draw Current Active Position Node (Matches Item #6 Telemetry Annotations)
        const currentPt = getActualPoint(maxT);
        const prevPt = getActualPoint(Math.max(0, maxT - 0.015));
        const headingRad = Math.atan2(currentPt.y - prevPt.y, currentPt.x - prevPt.x);
        const headingDeg = Math.round(((headingRad * 180 / Math.PI + 360) % 360));
        const currentSpeed = Math.round(15 + Math.sin(maxT * Math.PI * 3) * 35 + (maxT > 0.7 && maxT < 0.8 ? -30 : 0));
        const currentAlt = Math.round(2050 + maxT * 510);

        // Glowing pulse halo ring
        ctx.beginPath();
        ctx.arc(currentPt.x, currentPt.y, 10 + Math.sin(Date.now() / 150) * 3, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(currentPt.x, currentPt.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#FFFFFF';
        ctx.fill();

        // Direction Arrow inside node
        ctx.save();
        ctx.translate(currentPt.x, currentPt.y);
        ctx.rotate(headingRad);
        ctx.beginPath();
        ctx.moveTo(10, 0);
        ctx.lineTo(2, -4);
        ctx.lineTo(2, 4);
        ctx.closePath();
        ctx.fillStyle = '#FFFFFF';
        ctx.fill();
        ctx.restore();

        // 6. Floating Telemetry Annotation Callout (No giant card, minimal telemetry)
        ctx.font = '10px monospace';
        ctx.fillStyle = '#FFFFFF';
        ctx.fillText(`TIME: ${Math.floor(maxT * 42)}:${(Math.floor(maxT * 2520) % 60).toString().padStart(2, '0')}`, currentPt.x + 16, currentPt.y - 24);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.65)';
        ctx.fillText(`LAT ${(32.2431 + maxT * 0.065).toFixed(4)}°`, currentPt.x + 16, currentPt.y - 12);
        ctx.fillText(`LON ${(77.1892 - maxT * 0.041).toFixed(4)}°`, currentPt.x + 16, currentPt.y);
        ctx.fillText(`SPD ${currentSpeed} km/h`, currentPt.x + 16, currentPt.y + 12);
        ctx.fillText(`HDG ${headingDeg}°`, currentPt.x + 16, currentPt.y + 24);

        ctx.restore();
      }

      animFrameId.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animFrameId.current) cancelAnimationFrame(animFrameId.current);
      window.removeEventListener('resize', handleResize);
    };
  }, [viewMode, progress]);

  // Derived current metrics based on progress scrubber
  const currentMinutes = Math.floor(progress * 42);
  const currentSecs = Math.floor(progress * 2520) % 60;
  const timeFormatted = `${currentMinutes.toString().padStart(2, '0')}:${currentSecs.toString().padStart(2, '0')}`;
  const currentSpeed = Math.max(0, Math.round(18 + Math.sin(progress * Math.PI * 3) * 38 + (progress > 0.72 && progress < 0.8 ? -40 : 0)));

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
          ROUTE INTELLIGENCE
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl md:text-7xl font-medium tracking-tight text-white max-w-3xl leading-[1.08]"
        >
          Understand the route <br />
          <span className="font-serif italic font-normal text-white/90 tracking-normal">
            you actually took.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-6 text-base sm:text-lg text-white/60 max-w-2xl font-normal leading-relaxed"
        >
          Every GPS point along the trip is kept in order, so the path your group followed can be reconstructed and understood afterward.
        </motion.p>
      </section>

      {/* 3 & 4 & 5. HERO ROUTE VISUALIZATION + REPLAY SCRUBBER + PLANNED VS ACTUAL TOGGLE */}
      <section className="px-4 sm:px-6 max-w-6xl mx-auto my-6">
        
        {/* Minimal Mode Toggle Bar (Matches Item #5: PLANNED | ACTUAL | BOTH) */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4 font-mono text-xs text-white/50 border-b border-white/10 pb-4">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-white/40 uppercase tracking-widest">VIEW MODE:</span>
            <div className="flex items-center bg-white/5 border border-white/10 rounded-full p-0.5">
              {(['planned', 'actual', 'both'] as ViewMode[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={`px-3 py-1 rounded-full text-[11px] uppercase transition-all duration-200 ${
                    viewMode === mode
                      ? 'bg-white text-black font-semibold shadow-sm'
                      : 'hover:text-white text-white/60'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

          <div className="text-[11px] text-white/40 hidden sm:block">
            {viewMode === 'planned' && 'Showing intended route path only'}
            {viewMode === 'actual' && 'Showing recorded GPS actual path'}
            {viewMode === 'both' && 'Overlaying actual path (bright) on planned route (dashed)'}
          </div>
        </div>

        {/* Spatial Route Cartography Surface */}
        <div 
          onMouseMove={handleMouseMove}
          className="relative w-full h-[460px] sm:h-[540px] rounded-[24px] bg-[#030303] border border-white/10 overflow-hidden shadow-[0_30px_90px_rgba(0,0,0,0.95)] flex flex-col justify-between p-6 select-none"
        >
          {/* Canvas Background */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
          />

          {/* Minimal Top Overlay Legend */}
          <div className="relative z-20 flex justify-between items-start font-mono text-xs">
            <div className="flex items-center gap-4 text-white/70">
              <span className="flex items-center gap-2">
                <span className="w-4 h-[2px] bg-white/30 border-t border-dashed border-white" />
                PLANNED ROUTE
              </span>
              <span className="flex items-center gap-2">
                <span className="w-4 h-[3px] bg-white" />
                ACTUAL TRAJECTORY
              </span>
            </div>
            <div className="text-white/40 text-[11px]">
              RECONSTRUCTION ACCURACY: 99.4%
            </div>
          </div>

          {/* Bottom Controls Bar: Minimal Replay Scrubber + Speed Profile Graph */}
          <div className="relative z-20 bg-[#08080A]/90 border border-white/10 backdrop-blur-md rounded-xl p-4 space-y-3 font-mono text-xs">
            
            {/* Play/Pause & Scrubber Row (Item #4) */}
            <div className="flex items-center gap-4">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 border border-white/15 flex items-center justify-center text-white transition-colors shrink-0"
                title={isPlaying ? "Pause Replay" : "Play Replay"}
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
              </button>

              <div className="flex-1 flex items-center gap-3">
                <span className="text-[11px] text-white/50">{timeFormatted}</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.001"
                  value={progress}
                  onChange={(e) => setProgress(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-white/15 rounded-lg appearance-none cursor-pointer accent-white"
                />
                <span className="text-[11px] text-white/50">42:18</span>
              </div>

              <button
                onClick={() => setProgress(0)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-white/70 hover:text-white transition-colors shrink-0"
                title="Reset Replay"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* 7. SPEED VISUALIZATION (Synchronized Line Graph) */}
            <div className="pt-2 border-t border-white/10">
              <div className="flex justify-between text-[10px] text-white/40 mb-1">
                <span>SPEED PROFILE OVER TIME</span>
                <span className="text-white">{currentSpeed} km/h</span>
              </div>
              
              <div className="relative h-10 w-full bg-white/[0.02] rounded border border-white/5 overflow-hidden">
                {/* SVG Speed Curve */}
                <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 400 40">
                  <path
                    d="M 0 30 Q 80 15, 140 25 T 280 35 T 400 15"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.3)"
                    strokeWidth="1.5"
                  />
                  <path
                    d={`M 0 30 Q 80 15, 140 25 T 280 35 T 400 15 L ${progress * 400} 40 L 0 40 Z`}
                    fill="rgba(255, 255, 255, 0.08)"
                  />
                </svg>

                {/* Synchronized Vertical Indicator Line */}
                <div
                  className="absolute top-0 bottom-0 w-[2px] bg-white shadow-[0_0_8px_rgba(255,255,255,1)]"
                  style={{ left: `${progress * 100}%` }}
                />
              </div>
            </div>

          </div>

        </div>

        {/* 9. JOURNEY TIMELINE (Interactive Milestone Event Markers) */}
        <div className="mt-6 font-mono text-xs">
          <div className="text-[10px] text-white/40 uppercase tracking-widest mb-3">
            JOURNEY TIMELINE MILESTONES (CLICK TO JUMP)
          </div>
          
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {TIMELINE_EVENTS.map((ev) => (
              <button
                key={ev.label}
                onClick={() => {
                  setProgress(ev.progress);
                  setIsPlaying(false);
                }}
                className={`p-3 rounded-xl border text-left transition-all duration-200 ${
                  Math.abs(progress - ev.progress) < 0.08
                    ? 'bg-white/10 border-white text-white shadow-lg'
                    : 'bg-white/[0.02] border-white/10 text-white/60 hover:border-white/20 hover:text-white'
                }`}
              >
                <div className="flex items-center justify-between text-[10px] text-white/40 mb-1">
                  <span>{ev.timeStr}</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-white" />
                </div>
                <div className="font-bold tracking-wider text-xs text-white">{ev.label}</div>
                <div className="text-[10px] text-white/50 truncate mt-0.5">{ev.desc}</div>
              </button>
            ))}
          </div>
        </div>

      </section>

      {/* 10 & 11. "WHAT REALLY HAPPENED" NARRATIVE SECTION */}
      <section className="py-24 px-6 max-w-5xl mx-auto border-t border-white/5">
        <div className="max-w-3xl">
          <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">
            THE ACTUAL JOURNEY
          </div>
          
          <h2 className="text-3xl sm:text-5xl font-medium tracking-tight text-white leading-tight">
            The plan is only <br />
            <span className="font-serif italic font-normal text-white/85">
              the beginning.
            </span>
          </h2>

          <p className="mt-6 text-base sm:text-lg text-white/60 font-normal leading-relaxed">
            RALLY preserves the movement that actually happened — where the group went, when they moved, when they slowed down, and how the route changed.
          </p>
        </div>

        {/* Route Difference Scene (Animated Route Deviation Concept) */}
        <div className="mt-12 p-8 rounded-[24px] bg-[#030303] border border-white/10 relative overflow-hidden font-mono">
          <div className="flex items-center justify-between text-xs text-white/50 mb-6">
            <span>ROUTE DEVIATION ANALYSIS</span>
            <span className="text-amber-400 font-semibold">DEVIATION DETECTED @ 14:20</span>
          </div>

          <div className="h-48 w-full relative flex items-center justify-center">
            <svg className="w-full h-full" viewBox="0 0 600 160">
              {/* Planned Path */}
              <path
                d="M 50 120 Q 200 120, 350 120 T 550 120"
                fill="none"
                stroke="rgba(255, 255, 255, 0.2)"
                strokeWidth="2"
                strokeDasharray="4 6"
              />
              <text x="50" y="145" fill="rgba(255,255,255,0.4)" fontSize="10" fontFamily="monospace">PLANNED TRAIL</text>

              {/* Actual Diverged Path */}
              <path
                d="M 50 120 Q 200 120, 280 50 T 550 120"
                fill="none"
                stroke="#FFFFFF"
                strokeWidth="3"
              />
              <text x="280" y="35" fill="#f59e0b" fontSize="10" fontFamily="monospace" fontWeight="bold">ROUTE DEVIATION (+85m)</text>

              {/* Divergence Vector Callout */}
              <line x1="280" y1="50" x2="280" y2="120" stroke="#f59e0b" strokeWidth="1" strokeDasharray="3 3" />
            </svg>
          </div>
        </div>
      </section>

      {/* 12. TRIP RECONSTRUCTION CLIMAX SECTION */}
      <section className="py-20 px-6 max-w-5xl mx-auto border-t border-white/5">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-3">
            TRIP RECONSTRUCTION PIPELINE
          </div>
          <h3 className="text-2xl sm:text-4xl font-medium text-white tracking-tight">
            How raw movement becomes intelligence.
          </h3>
        </div>

        {/* 4 Sequential Stage Selector */}
        <div className="flex flex-wrap items-center justify-center gap-3 mb-10 font-mono text-xs">
          {[
            { id: 'points', label: '1. GPS POINTS' },
            { id: 'connected', label: '2. CONNECTED PATH' },
            { id: 'journey', label: '3. JOURNEY' },
            { id: 'understood', label: '4. UNDERSTOOD' },
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => setReconstructStage(st.id as any)}
              className={`px-4 py-2 rounded-full border transition-all duration-200 ${
                reconstructStage === st.id
                  ? 'bg-white text-black font-semibold border-white shadow-md'
                  : 'bg-white/5 border-white/10 text-white/60 hover:text-white'
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>

        {/* Reconstruction Visual Canvas Box */}
        <div className="p-8 sm:p-12 rounded-[24px] bg-[#040405] border border-white/10 min-h-[300px] flex flex-col items-center justify-center relative font-mono">
          <svg className="w-full max-w-3xl h-48" viewBox="0 0 600 160">
            {/* Raw Points */}
            {(reconstructStage === 'points' || reconstructStage === 'connected' || reconstructStage === 'journey' || reconstructStage === 'understood') && (
              <g>
                {[...Array(16)].map((_, i) => {
                  const x = 50 + i * 33;
                  const y = 80 + Math.sin(i * 0.6) * 35;
                  return (
                    <circle
                      key={i}
                      cx={x}
                      cy={y}
                      r={reconstructStage === 'points' ? 3 : 2}
                      fill={reconstructStage === 'points' ? '#38bdf8' : '#ffffff'}
                    />
                  );
                })}
              </g>
            )}

            {/* Connected Path */}
            {(reconstructStage === 'connected' || reconstructStage === 'journey' || reconstructStage === 'understood') && (
              <path
                d="M 50 80 Q 150 140, 250 50 T 450 110 T 550 80"
                fill="none"
                stroke="#FFFFFF"
                strokeWidth="2.5"
              />
            )}

            {/* Understood Floating Labels */}
            {reconstructStage === 'understood' && (
              <g fill="#FFFFFF" fontSize="10" fontFamily="monospace">
                <rect x="70" y="20" width="100" height="24" rx="4" fill="#000" stroke="rgba(255,255,255,0.2)" />
                <text x="80" y="36" fill="#38bdf8">DIST: 14.2 km</text>

                <rect x="230" y="110" width="100" height="24" rx="4" fill="#000" stroke="rgba(255,255,255,0.2)" />
                <text x="240" y="126" fill="#f59e0b">DEVIATIONS: 2</text>

                <rect x="420" y="20" width="110" height="24" rx="4" fill="#000" stroke="rgba(255,255,255,0.2)" />
                <text x="430" y="36" fill="#34d399">MAX SPD: 68 km/h</text>
              </g>
            )}
          </svg>

          <div className="mt-6 text-center text-xs text-white/60 max-w-md">
            {reconstructStage === 'points' && 'Dozens of high-frequency GPS positions recorded directly on mobile device sensors.'}
            {reconstructStage === 'connected' && 'Locations ordered by device timestamp, eliminating network delivery latency scrambling.'}
            {reconstructStage === 'journey' && 'The complete trajectory reconstructed as a continuous, high-fidelity spatial curve.'}
            {reconstructStage === 'understood' && 'Automatic metadata extraction: pace changes, stops, elevation profiles, and deviations.'}
          </div>
        </div>
      </section>

      {/* 13. EDITORIAL FEATURE STATEMENTS (Hover Statements, NO CARDS) */}
      <section className="py-20 px-6 max-w-4xl mx-auto border-t border-white/5 font-sans">
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-10 text-center">
          FOUNDATIONAL PRINCIPLES
        </div>

        <div className="space-y-6">
          {[
            { statement: 'Every point has a place.', detail: 'High-precision latitude, longitude, and elevation captured with sub-meter spatial accuracy.' },
            { statement: 'Every point has a time.', detail: 'Device-assigned UTC timestamps preserve true chronological order regardless of cell signal drops.' },
            { statement: 'Every point has a direction.', detail: '360° heading vectors clarify travel direction, turn dynamics, and orientation.' },
            { statement: 'Every point tells part of the journey.', detail: 'PostGIS spatial analytics aggregate individual telemetry readings into complete trip memory.' },
          ].map((item, idx) => (
            <div
              key={idx}
              onMouseEnter={() => setActiveStatementHover(idx)}
              onMouseLeave={() => setActiveStatementHover(null)}
              className={`p-6 rounded-2xl border transition-all duration-300 cursor-pointer ${
                activeStatementHover === idx
                  ? 'bg-white/[0.05] border-white/30 text-white'
                  : 'bg-white/[0.02] border-white/10 text-white/80'
              }`}
            >
              <div className="text-xl sm:text-2xl font-medium tracking-tight flex items-center justify-between">
                <span>{item.statement}</span>
                <ChevronRight className={`w-5 h-5 transition-transform ${activeStatementHover === idx ? 'translate-x-1 text-white' : 'text-white/30'}`} />
              </div>
              
              <AnimatePresence>
                {activeStatementHover === idx && (
                  <motion.p
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-3 text-sm text-white/60 font-mono leading-relaxed"
                  >
                    {item.detail}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </section>

      {/* 14. MINIMAL FINAL CTA */}
      <section className="pb-28 px-6 max-w-3xl mx-auto text-center">
        <div className="pt-16 border-t border-white/10 flex flex-col items-center">
          <h3 className="text-3xl sm:text-5xl font-medium text-white tracking-tight">
            Understand every journey.
          </h3>

          <p className="mt-4 text-base text-white/60 font-normal font-sans">
            RALLY keeps the trip after the trip is over.
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
