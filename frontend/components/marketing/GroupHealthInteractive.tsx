'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  HeartPulse, 
  Crown, 
  Users, 
  ShieldCheck, 
  Activity, 
  ChevronRight, 
  Lock, 
  Radio 
} from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

type HealthState = 'healthy' | 'attention' | 'risk' | 'recovered';

interface HealthStateConfig {
  id: HealthState;
  label: string;
  targetScore: number;
  statusText: string;
  color: string;
  togetherVal: number;
  onRouteVal: number;
  connectedVal: number;
  stableVal: number;
}

const HEALTH_STATES: HealthStateConfig[] = [
  {
    id: 'healthy',
    label: 'HEALTHY',
    targetScore: 92,
    statusText: 'GROUP IS TOGETHER',
    color: '#34d399', // emerald
    togetherVal: 98,
    onRouteVal: 95,
    connectedVal: 100,
    stableVal: 92,
  },
  {
    id: 'attention',
    label: 'ATTENTION',
    targetScore: 78,
    statusText: 'GROUP NEEDS ATTENTION',
    color: '#fbbf24', // amber
    togetherVal: 72,
    onRouteVal: 88,
    connectedVal: 94,
    stableVal: 76,
  },
  {
    id: 'risk',
    label: 'RISK',
    targetScore: 61,
    statusText: 'GROUP IS SEPARATING',
    color: '#f87171', // red
    togetherVal: 48,
    onRouteVal: 75,
    connectedVal: 80,
    stableVal: 52,
  },
  {
    id: 'recovered',
    label: 'RECOVERED',
    targetScore: 89,
    statusText: 'GROUP IS TOGETHER AGAIN',
    color: '#34d399', // emerald
    togetherVal: 94,
    onRouteVal: 92,
    connectedVal: 98,
    stableVal: 88,
  },
];

export default function GroupHealthInteractive() {
  const [currentStateId, setCurrentStateId] = useState<HealthState>('healthy');
  const [displayScore, setDisplayScore] = useState<number>(92);
  const [activeMemberCount, setActiveMemberCount] = useState<number>(5);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameId = useRef<number | null>(null);
  const mousePos = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });

  const activeConfig = HEALTH_STATES.find((s) => s.id === currentStateId) || HEALTH_STATES[0];

  // Smooth numerical score interpolation (e.g. 92 -> 78 -> 61 -> 89)
  useEffect(() => {
    let animId: number;
    const animateScore = () => {
      setDisplayScore((prev) => {
        const diff = activeConfig.targetScore - prev;
        if (Math.abs(diff) < 0.2) return activeConfig.targetScore;
        return prev + diff * 0.08;
      });
      animId = requestAnimationFrame(animateScore);
    };
    animId = requestAnimationFrame(animateScore);
    return () => cancelAnimationFrame(animId);
  }, [activeConfig.targetScore]);

  // Handle Mouse movement for subtle 60fps parallax effect (inertia damped)
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (typeof window === 'undefined' || window.innerWidth < 768) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2);
    const y = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2);
    mousePos.current.targetX = x * 15;
    mousePos.current.targetY = y * 10;
  }, []);

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

    const members = [
      { id: '1', name: 'Rahul', role: 'LEADER', baseAngle: 0, baseRadius: 150 },
      { id: '2', name: 'Keshav', role: 'MEMBER', baseAngle: 1.2, baseRadius: 160 },
      { id: '3', name: 'Aditi', role: 'MEMBER', baseAngle: 2.5, baseRadius: 145 },
      { id: '4', name: 'Priya', role: 'MEMBER', baseAngle: 3.8, baseRadius: 170 },
      { id: '5', name: 'You', role: 'MEMBER', baseAngle: 5.1, baseRadius: 155 },
    ];

    const render = () => {
      // Damped parallax mouse interpolation
      mousePos.current.x += (mousePos.current.targetX - mousePos.current.x) * 0.05;
      mousePos.current.y += (mousePos.current.targetY - mousePos.current.y) * 0.05;
      const ox = mousePos.current.x;
      const oy = mousePos.current.y;

      ctx.clearRect(0, 0, width, height);

      const centerX = width / 2;
      const centerY = height / 2;
      const time = Date.now() / 1000;

      // 1. Draw Subtle Organic Radial Grid Rings
      ctx.save();
      ctx.translate(ox * 0.3, oy * 0.3);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
      ctx.lineWidth = 1;
      
      [100, 160, 220].forEach((r) => {
        ctx.beginPath();
        ctx.arc(centerX, centerY, r + Math.sin(time + r) * 2, 0, Math.PI * 2);
        ctx.stroke();
      });
      ctx.restore();

      // 2. Calculate Member Node Positions
      ctx.save();
      ctx.translate(ox * 0.6, oy * 0.6);

      const nodeCoords: { x: number; y: number; name: string; role: string; isSeparated: boolean }[] = [];

      members.forEach((m, idx) => {
        if (idx >= activeMemberCount) return; // respect active membership toggle

        let angle = m.baseAngle + time * 0.15;
        let radius = m.baseRadius;
        let isSeparated = false;

        // Apply separation offset if in ATTENTION or RISK states (Keshav m.id === '2')
        if (currentStateId === 'attention' && m.id === '2') {
          radius += 60;
          isSeparated = true;
        } else if (currentStateId === 'risk' && m.id === '2') {
          radius += 120;
          isSeparated = true;
        }

        const nx = centerX + Math.cos(angle) * radius;
        const ny = centerY + Math.sin(angle) * (radius * 0.65); // slight elliptical tilt
        nodeCoords.push({ x: nx, y: ny, name: m.name, role: m.role, isSeparated });
      });

      // 3. Draw Connecting Vector Network Lines
      ctx.beginPath();
      for (let i = 0; i < nodeCoords.length; i++) {
        for (let j = i + 1; j < nodeCoords.length; j++) {
          const n1 = nodeCoords[i];
          const n2 = nodeCoords[j];
          ctx.moveTo(n1.x, n1.y);
          ctx.lineTo(n2.x, n2.y);
        }
      }
      ctx.strokeStyle = currentStateId === 'risk' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // 4. Draw Individual Member Nodes
      nodeCoords.forEach((n) => {
        // Node Fill
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.role === 'LEADER' ? 6 : 4, 0, Math.PI * 2);
        ctx.fillStyle = n.isSeparated ? '#f59e0b' : '#FFFFFF';
        ctx.fill();

        // Glowing Ring for Leader or Separated Node
        if (n.role === 'LEADER') {
          ctx.beginPath();
          ctx.arc(n.x, n.y, 11 + Math.sin(time * 3) * 2, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
          ctx.lineWidth = 1;
          ctx.stroke();
        } else if (n.isSeparated) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, 14 + Math.sin(time * 4) * 3, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(245, 158, 11, 0.6)';
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // Node Label
        ctx.font = '10px monospace';
        ctx.fillStyle = n.isSeparated ? '#f59e0b' : 'rgba(255, 255, 255, 0.7)';
        ctx.fillText(n.name + (n.role === 'LEADER' ? ' (LEADER)' : ''), n.x + 9, n.y + 3);
      });

      ctx.restore();

      animFrameId.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animFrameId.current) cancelAnimationFrame(animFrameId.current);
      window.removeEventListener('resize', handleResize);
    };
  }, [currentStateId, activeMemberCount]);

  return (
    <div className="bg-[#000000] text-white min-h-screen font-sans selection:bg-white/20 selection:text-white">
      {/* Global Navbar */}
      <Navbar />

      {/* 2. HERO SECTION */}
      <section className="pt-16 pb-6 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono tracking-[0.2em] text-white/70 uppercase mb-6"
        >
          <span 
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ backgroundColor: activeConfig.color }}
          />
          GROUP HEALTH
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl md:text-7xl font-medium tracking-tight text-white max-w-3xl leading-[1.08]"
        >
          One number for <br />
          <span className="font-serif italic font-normal text-white/90 tracking-normal">
            how the group is doing.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-6 text-base sm:text-lg text-white/60 max-w-2xl font-normal leading-relaxed"
        >
          Instead of watching every member individually, get a single, honest read on whether the group is together and on track.
        </motion.p>
      </section>

      {/* 3 & 4 & 5. MAIN GROUP HEALTH VISUALIZATION (Dominant Score + Radial Member Network) */}
      <section className="px-4 sm:px-6 max-w-6xl mx-auto my-6">
        
        {/* Minimal Interactive State Selector Bar (Matches Item #11) */}
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4 mb-6 font-mono text-xs text-white/50 border-b border-white/10 pb-4">
          {HEALTH_STATES.map((st, idx) => {
            const isActive = currentStateId === st.id;
            return (
              <React.Fragment key={st.id}>
                {idx > 0 && <span className="text-white/20 hidden sm:inline">───</span>}
                <button
                  onClick={() => setCurrentStateId(st.id)}
                  className={`px-3 py-1.5 rounded-full transition-all duration-200 flex items-center gap-2 ${
                    isActive
                      ? 'bg-white text-black font-semibold shadow-[0_0_20px_rgba(255,255,255,0.2)]'
                      : 'hover:text-white hover:bg-white/5'
                  }`}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: st.color }}
                  />
                  <span>{st.label}</span>
                </button>
              </React.Fragment>
            );
          })}
        </div>

        {/* Spatial Canvas Surface Container */}
        <div 
          onMouseMove={handleMouseMove}
          className="relative w-full h-[480px] sm:h-[560px] rounded-[24px] bg-[#030303] border border-white/10 overflow-hidden shadow-[0_30px_90px_rgba(0,0,0,0.95)] flex flex-col justify-between p-6 select-none"
        >
          {/* HTML5 Radial Network Canvas */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
          />

          {/* Top Bar Readout */}
          <div className="relative z-20 flex justify-between items-start font-mono text-xs">
            <div className="flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full animate-pulse"
                style={{ backgroundColor: activeConfig.color }}
              />
              <span className="text-white uppercase font-bold tracking-wider">{activeConfig.statusText}</span>
            </div>

            <div className="text-white/40 text-[11px] flex items-center gap-3">
              <span>ACTIVE MEMBERS: {activeMemberCount}</span>
              <button
                onClick={() => setActiveMemberCount((prev) => (prev === 5 ? 4 : 5))}
                className="px-2 py-0.5 rounded border border-white/20 text-white/70 hover:text-white hover:border-white transition-colors"
              >
                TOGGLE MEMBERSHIP ({activeMemberCount === 5 ? 'LEAVE' : 'REJOIN'})
              </button>
            </div>
          </div>

          {/* 4. DOMINANT CENTRAL SCORE (140px Large Number at Center) */}
          <div className="relative z-20 flex flex-col items-center justify-center pointer-events-none my-auto">
            <div className="text-8xl sm:text-[140px] font-light tracking-tighter text-white leading-none font-sans drop-shadow-[0_0_50px_rgba(255,255,255,0.15)]">
              {Math.round(displayScore)}
            </div>

            <div className="mt-2 font-mono text-xs tracking-[0.25em] text-white/50 uppercase">
              GROUP HEALTH INDEX
            </div>

            {/* 5. State Indicators Below Score */}
            <div className="mt-4 flex flex-wrap items-center justify-center gap-3 sm:gap-6 font-mono text-[11px] text-white/70">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> TOGETHER
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> ON ROUTE
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> CONNECTED
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> STABLE
              </span>
            </div>
          </div>

          {/* 7. HEALTH DIMENSIONS (Minimal Thin Lines, NO CARDS) */}
          <div className="relative z-20 bg-[#08080A]/85 border border-white/10 backdrop-blur-md rounded-xl p-4 font-mono text-xs">
            <div className="text-[10px] text-white/40 uppercase tracking-widest mb-2">
              HEALTH DIMENSION BREAKDOWN
            </div>
            
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="text-white/60">TOGETHER</span>
                  <span className="text-white font-bold">{activeConfig.togetherVal}%</span>
                </div>
                <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full transition-all duration-500 rounded-full"
                    style={{ width: `${activeConfig.togetherVal}%`, backgroundColor: activeConfig.color }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="text-white/60">ON ROUTE</span>
                  <span className="text-white font-bold">{activeConfig.onRouteVal}%</span>
                </div>
                <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full transition-all duration-500 rounded-full"
                    style={{ width: `${activeConfig.onRouteVal}%`, backgroundColor: activeConfig.color }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="text-white/60">CONNECTED</span>
                  <span className="text-white font-bold">{activeConfig.connectedVal}%</span>
                </div>
                <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full transition-all duration-500 rounded-full"
                    style={{ width: `${activeConfig.connectedVal}%`, backgroundColor: activeConfig.color }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] mb-1">
                  <span className="text-white/60">STABLE</span>
                  <span className="text-white font-bold">{activeConfig.stableVal}%</span>
                </div>
                <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full transition-all duration-500 rounded-full"
                    style={{ width: `${activeConfig.stableVal}%`, backgroundColor: activeConfig.color }}
                  />
                </div>
              </div>
            </div>
          </div>

        </div>

      </section>

      {/* 13 & 14. EXPLANATION & SIGNAL CONVERGENCE FLOW SECTION */}
      <section className="py-24 px-6 max-w-4xl mx-auto text-center border-t border-white/5">
        <div className="text-xs font-mono text-white/40 uppercase tracking-widest mb-4">
          HOW HEALTH IS CALCULATED
        </div>

        <h2 className="text-3xl sm:text-5xl md:text-6xl font-medium tracking-tight text-white leading-tight">
          One group. <br />
          <span className="font-serif italic font-normal text-white/85">
            One shared state.
          </span>
        </h2>

        <p className="mt-6 text-base sm:text-lg text-white/60 max-w-xl mx-auto font-normal leading-relaxed">
          Group Health combines the signals that matter across the trip into one clear picture, so you can understand the condition of the group without watching every member separately.
        </p>

        {/* 14. Signal Convergence Diagram (NO Cards, Typography + Thin Lines) */}
        <div className="mt-16 max-w-3xl mx-auto font-mono text-xs">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-white/70">
            <div className="flex flex-col items-center">
              <span className="font-bold tracking-widest text-white uppercase">5 MEMBERS</span>
              <span className="text-[10px] text-white/40 mt-0.5">GPS Positions</span>
            </div>

            <span className="text-white/30">+</span>

            <div className="flex flex-col items-center">
              <span className="font-bold tracking-widest text-white uppercase">MOVEMENT</span>
              <span className="text-[10px] text-white/40 mt-0.5">Vector Speeds</span>
            </div>

            <span className="text-white/30">+</span>

            <div className="flex flex-col items-center">
              <span className="font-bold tracking-widest text-white uppercase">CONNECTED</span>
              <span className="text-[10px] text-white/40 mt-0.5">Signal Pings</span>
            </div>

            <span className="text-white/30">=</span>

            <div className="flex flex-col items-center p-3 rounded-xl bg-white/10 border border-white/20">
              <span className="font-bold tracking-widest text-emerald-400 uppercase">HEALTH SCORE</span>
              <span className="text-[10px] text-emerald-400/70 mt-0.5">Single Honest Read</span>
            </div>
          </div>
        </div>
      </section>

      {/* 16 & 17. PRIVACY STATEMENT & TRIP SHAPE HEALTH TIMELINE */}
      <section className="py-20 px-6 max-w-4xl mx-auto border-t border-white/5 font-mono text-xs">
        
        {/* 17. Trip Shape Timeline */}
        <div className="mb-16">
          <div className="text-[10px] text-white/40 uppercase tracking-widest mb-4 text-center">
            HEALTH TRAJECTORY ACROSS TRIP SHAPE
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-6 rounded-2xl bg-[#030303] border border-white/10">
            <div className="text-center sm:text-left">
              <span className="text-[10px] text-white/40 block">START</span>
              <span className="text-xl font-bold text-emerald-400">92</span>
            </div>

            <div className="hidden sm:block flex-1 h-[1px] bg-gradient-to-r from-emerald-400 via-amber-400 to-emerald-400 mx-4" />

            <div className="text-center">
              <span className="text-[10px] text-white/40 block">SOLANG ASCENT</span>
              <span className="text-xl font-bold text-amber-400">76</span>
            </div>

            <div className="hidden sm:block flex-1 h-[1px] bg-gradient-to-r from-amber-400 to-emerald-400 mx-4" />

            <div className="text-center sm:text-right">
              <span className="text-[10px] text-white/40 block">DESTINATION</span>
              <span className="text-xl font-bold text-emerald-400">91</span>
            </div>
          </div>
        </div>

        {/* 16. Subtle Privacy Statement (NO GIANT LOCK GRAPHIC!) */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl bg-white/[0.02] border border-white/10 text-white/60">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-white/40" />
            <span>Your group's movement stays within the group.</span>
          </div>
          <div className="text-[11px] text-white/40 font-mono">
            PRIVATE GROUP ●●●●●
          </div>
        </div>

      </section>

      {/* 18 & 19. FINAL SECTION & MINIMAL CTA */}
      <section className="pb-28 px-6 max-w-3xl mx-auto text-center">
        <div className="pt-16 border-t border-white/10 flex flex-col items-center">
          <h3 className="text-3xl sm:text-5xl font-medium text-white tracking-tight">
            Know how the group is doing.
          </h3>

          <p className="mt-4 text-base text-white/60 font-normal font-sans">
            One clear signal. The whole trip.
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
