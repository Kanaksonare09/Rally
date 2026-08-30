'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, AlertTriangle, Radio, Navigation, Eye, CheckCircle2, ChevronRight, Activity, MapPin } from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

type ScenarioType = 'falling_behind' | 'route_deviation' | 'unexpected_stop' | 'connectivity_loss';

interface MemberPoint {
  id: string;
  name: string;
  baseOffsetU: number; // offset along route curve
  baseOffsetV: number; // perpendicular distance from route
  color: string;
}

const MEMBERS: MemberPoint[] = [
  { id: '1', name: 'Rahul', baseOffsetU: 0.08, baseOffsetV: -12, color: '#38bdf8' },
  { id: '2', name: 'Keshav', baseOffsetU: 0.04, baseOffsetV: 15, color: '#fbbf24' },
  { id: '3', name: 'Aditi', baseOffsetU: 0.00, baseOffsetV: -8, color: '#38bdf8' },
  { id: '4', name: 'Priya', baseOffsetU: -0.05, baseOffsetV: 10, color: '#38bdf8' },
  { id: '5', name: 'You', baseOffsetU: -0.09, baseOffsetV: -5, color: '#ffffff' },
];

const SCENARIOS: { id: ScenarioType; label: string; tag: string }[] = [
  { id: 'falling_behind', label: 'FALLING BEHIND', tag: 'Sustained Distance Increase' },
  { id: 'route_deviation', label: 'ROUTE DEVIATION', tag: 'Off-Trail Vector Divergence' },
  { id: 'unexpected_stop', label: 'UNEXPECTED STOP', tag: 'Duration > Threshold @ 0 km/h' },
  { id: 'connectivity_loss', label: 'CONNECTIVITY LOSS', tag: 'Missed Heartbeat & Telemetry Loss' },
];

export default function SmartAlertsInteractive() {
  const [activeScenario, setActiveScenario] = useState<ScenarioType>('falling_behind');
  const [simPhase, setSimPhase] = useState<'normal' | 'anomaly' | 'analysis' | 'triggered'>('normal');
  const [elapsedSec, setElapsedSec] = useState<number>(0);
  
  // Canvas and Animation Refs
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameId = useRef<number | null>(null);
  const startTimeRef = useRef<number>(Date.now());
  const mousePos = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Reset sequence when scenario changes
  const changeScenario = useCallback((scenario: ScenarioType) => {
    setActiveScenario(scenario);
    setSimPhase('normal');
    setElapsedSec(0);
    startTimeRef.current = Date.now();
  }, []);

  // Handle Mouse movement for subtle 60fps parallax effect (inertia damped)
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (typeof window === 'undefined' || window.innerWidth < 768) return; // disabled on mobile
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2);
    const y = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2);
    mousePos.current.targetX = x * 20; // 20px max tilt
    mousePos.current.targetY = y * 15;
  }, []);

  // Main Canvas Render Loop (requestAnimationFrame @ 60fps)
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

    // Route curve points (S-curve through spatial field)
    const getRoutePoint = (u: number, offsetV: number = 0) => {
      // u from 0 to 1
      const cx = width * 0.15 + u * width * 0.75;
      const cy = height * 0.7 - Math.sin(u * Math.PI * 1.5) * height * 0.35;
      
      // Normal vector for perpendicular offset
      const du = 0.005;
      const nx1 = width * 0.15 + (u + du) * width * 0.75;
      const ny1 = height * 0.7 - Math.sin((u + du) * Math.PI * 1.5) * height * 0.35;
      const dx = nx1 - cx;
      const dy = ny1 - cy;
      const len = Math.sqrt(dx * dx + dy * dy) || 1;
      const px = -dy / len;
      const py = dx / len;

      return {
        x: cx + px * offsetV,
        y: cy + py * offsetV,
        angle: Math.atan2(dy, dx)
      };
    };

    const render = () => {
      const now = Date.now();
      const elapsed = (now - startTimeRef.current) / 1000;
      setElapsedSec(Math.min(elapsed, 12));

      // Phase calculation based on time
      let phase: 'normal' | 'anomaly' | 'analysis' | 'triggered' = 'normal';
      if (elapsed > 2.5 && elapsed <= 5.5) phase = 'anomaly';
      else if (elapsed > 5.5 && elapsed <= 7.5) phase = 'analysis';
      else if (elapsed > 7.5) phase = 'triggered';
      setSimPhase(phase);

      // Smooth mouse parallax damping
      mousePos.current.x += (mousePos.current.targetX - mousePos.current.x) * 0.05;
      mousePos.current.y += (mousePos.current.targetY - mousePos.current.y) * 0.05;

      const offsetX = mousePos.current.x;
      const offsetY = mousePos.current.y;

      // Clear Canvas
      ctx.clearRect(0, 0, width, height);

      // 1. Draw Subtle Topo/Spatial Grid Lines
      ctx.save();
      ctx.translate(offsetX * 0.3, offsetY * 0.3);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
      ctx.lineWidth = 1;
      const gridSize = 48;
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      ctx.restore();

      // 2. Draw Main Route Curve Line
      ctx.save();
      ctx.translate(offsetX * 0.6, offsetY * 0.6);
      
      ctx.beginPath();
      for (let u = 0; u <= 1; u += 0.01) {
        const pt = getRoutePoint(u);
        if (u === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      }
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 6]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Base progress of group along route (loops every 12 seconds)
      const groupProgress = ((elapsed * 0.04) % 0.6) + 0.2;

      // 3. Draw Member Positions & Anomaly Behaviors
      const memberCoords: { x: number; y: number; name: string; isTarget: boolean; color: string }[] = [];

      MEMBERS.forEach((m) => {
        let u = groupProgress + m.baseOffsetU;
        let v = m.baseOffsetV;
        let isTarget = false;
        let overrideColor = m.color;

        // SCENARIO 1: FALLING BEHIND (Keshav m.id === '2')
        if (activeScenario === 'falling_behind' && m.id === '2') {
          isTarget = true;
          if (elapsed > 2.5) {
            const lagAmount = Math.min((elapsed - 2.5) * 0.025, 0.12);
            u -= lagAmount;
            overrideColor = elapsed > 5.5 ? '#f59e0b' : '#38bdf8';
          }
        }

        // SCENARIO 2: ROUTE DEVIATION (Priya m.id === '4')
        if (activeScenario === 'route_deviation' && m.id === '4') {
          isTarget = true;
          if (elapsed > 2.5) {
            const devAmount = Math.min((elapsed - 2.5) * 18, 75);
            v += devAmount;
            overrideColor = elapsed > 5.5 ? '#f59e0b' : '#38bdf8';
          }
        }

        // SCENARIO 3: UNEXPECTED STOP (Aditi m.id === '3')
        if (activeScenario === 'unexpected_stop' && m.id === '3') {
          isTarget = true;
          if (elapsed > 2.5) {
            // freeze u progress
            u = ((2.5 * 0.04) % 0.6) + 0.2 + m.baseOffsetU;
            overrideColor = elapsed > 5.5 ? '#ef4444' : '#38bdf8';
          }
        }

        // SCENARIO 4: CONNECTIVITY LOSS (Rahul m.id === '1')
        if (activeScenario === 'connectivity_loss' && m.id === '1') {
          isTarget = true;
          if (elapsed > 2.5) {
            overrideColor = 'rgba(255, 255, 255, 0.3)';
          }
        }

        const pos = getRoutePoint(Math.max(0, Math.min(1, u)), v);
        memberCoords.push({ x: pos.x, y: pos.y, name: m.name, isTarget, color: overrideColor });
      });

      // Find group centroid
      const normalMembers = memberCoords.filter((m) => !m.isTarget || phase === 'normal');
      const centroidX = normalMembers.reduce((acc, m) => acc + m.x, 0) / (normalMembers.length || 1);
      const centroidY = normalMembers.reduce((acc, m) => acc + m.y, 0) / (normalMembers.length || 1);

      // Draw connection vectors between target and group centroid during anomaly/analysis
      const targetMember = memberCoords.find((m) => m.isTarget);
      if (targetMember && phase !== 'normal') {
        ctx.beginPath();
        ctx.moveTo(centroidX, centroidY);
        ctx.lineTo(targetMember.x, targetMember.y);
        ctx.strokeStyle = phase === 'triggered' ? 'rgba(245, 158, 11, 0.4)' : 'rgba(255, 255, 255, 0.2)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Distance HUD line label
        const midX = (centroidX + targetMember.x) / 2;
        const midY = (centroidY + targetMember.y) / 2;
        const distPx = Math.round(Math.hypot(targetMember.x - centroidX, targetMember.y - centroidY));
        
        ctx.font = '10px monospace';
        ctx.fillStyle = phase === 'triggered' ? '#f59e0b' : 'rgba(255, 255, 255, 0.6)';
        ctx.fillText(`${distPx * 2}m`, midX + 6, midY - 6);
      }

      // Draw each member point
      memberCoords.forEach((m) => {
        // Draw Member Dot
        ctx.beginPath();
        ctx.arc(m.x, m.y, m.name === 'You' ? 5 : 4, 0, Math.PI * 2);
        ctx.fillStyle = m.color;
        ctx.fill();

        // Glow ring for target anomaly or You
        if (m.isTarget && phase !== 'normal') {
          ctx.beginPath();
          ctx.arc(m.x, m.y, 10 + Math.sin(now / 150) * 3, 0, Math.PI * 2);
          ctx.strokeStyle = m.color;
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // Connectivity Loss Ghost Pulse
        if (activeScenario === 'connectivity_loss' && m.name === 'Rahul' && phase !== 'normal') {
          ctx.beginPath();
          ctx.arc(m.x, m.y, 16 + (now % 1000) / 40, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(255, 255, 255, ${0.4 - ((now % 1000) / 2500)})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // Member Label
        ctx.font = '11px monospace';
        ctx.fillStyle = m.isTarget && phase !== 'normal' ? m.color : 'rgba(255, 255, 255, 0.7)';
        ctx.fillText(m.name, m.x + 8, m.y + 3);
      });

      ctx.restore();

      // Request next frame
      animFrameId.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animFrameId.current) cancelAnimationFrame(animFrameId.current);
      window.removeEventListener('resize', handleResize);
    };
  }, [activeScenario, changeScenario]);

  return (
    <div className="bg-[#000000] text-white min-h-screen font-sans selection:bg-white/20 selection:text-white">
      {/* Header */}
      <Navbar />

      {/* 1. HERO SECTION */}
      <section className="pt-16 pb-6 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono tracking-[0.2em] text-white/70 uppercase mb-6"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
          SMART ALERTS
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl md:text-7xl font-medium tracking-tight text-white max-w-3xl leading-[1.08]"
        >
          Know the moment <br />
          <span className="font-serif italic font-normal text-white/90 tracking-normal">
            something needs attention.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-6 text-base sm:text-lg text-white/60 max-w-2xl font-normal leading-relaxed"
        >
          RALLY watches the shape of the trip as it happens, so the group finds out about a problem before it becomes an emergency.
        </motion.p>
      </section>

      {/* 2. MAIN INTERACTIVE VISUALIZATION (Group Movement Intelligence Canvas) */}
      <section className="px-4 sm:px-6 max-w-6xl mx-auto my-6">
        
        {/* Minimal Scenario Signal Selector Bar (Matches Item #7 & #12) */}
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4 mb-6 font-mono text-xs text-white/50 border-b border-white/10 pb-4">
          {SCENARIOS.map((sc, idx) => {
            const isActive = activeScenario === sc.id;
            return (
              <React.Fragment key={sc.id}>
                {idx > 0 && <span className="text-white/20 hidden sm:inline">───</span>}
                <button
                  onClick={() => changeScenario(sc.id)}
                  className={`px-3 py-1.5 rounded-full transition-all duration-200 flex items-center gap-2 ${
                    isActive
                      ? 'bg-white text-black font-semibold shadow-[0_0_20px_rgba(255,255,255,0.2)]'
                      : 'hover:text-white hover:bg-white/5'
                  }`}
                >
                  <span>{sc.label}</span>
                </button>
              </React.Fragment>
            );
          })}
        </div>

        {/* Spatial Visualization Container */}
        <div 
          ref={containerRef}
          onMouseMove={handleMouseMove}
          className="relative w-full h-[480px] sm:h-[560px] rounded-[24px] bg-[#030303] border border-white/10 overflow-hidden shadow-[0_30px_90px_rgba(0,0,0,0.95)] flex flex-col justify-between p-6 select-none"
        >
          {/* Top Left Status Typography (Matches Item #3: Tiny typography near visualization, NO giant card) */}
          <div className="relative z-20 flex justify-between items-start">
            <div className="font-mono text-xs tracking-wider">
              <div className="text-[10px] text-white/40 uppercase tracking-widest">GROUP STATUS</div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`w-2 h-2 rounded-full ${
                  simPhase === 'normal' ? 'bg-emerald-400' : simPhase === 'triggered' ? 'bg-amber-400 animate-pulse' : 'bg-amber-400'
                }`} />
                <span className="text-white font-medium uppercase">
                  {simPhase === 'normal' && 'ALL TOGETHER'}
                  {simPhase === 'anomaly' && 'MOVEMENT CHANGING...'}
                  {simPhase === 'analysis' && 'ANALYZING PATTERN'}
                  {simPhase === 'triggered' && 'ANOMALY DETECTED'}
                </span>
              </div>
            </div>

            {/* Scenario Tag Readout */}
            <div className="font-mono text-[11px] text-white/40 hidden sm:block">
              {SCENARIOS.find(s => s.id === activeScenario)?.tag}
            </div>
          </div>

          {/* HTML5 Canvas Surface */}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
          />

          {/* 5. INTELLIGENCE MOMENT OVERLAY (Appears dynamically during analysis phase) */}
          <AnimatePresence>
            {(simPhase === 'analysis' || simPhase === 'triggered') && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                transition={{ duration: 0.3 }}
                className="absolute top-20 left-6 z-20 font-mono text-[11px] text-white/80 p-3 rounded-lg bg-black/80 border border-white/15 backdrop-blur-md max-w-xs shadow-2xl space-y-1"
              >
                <div className="text-[9px] text-white/40 tracking-widest uppercase mb-1 flex items-center justify-between">
                  <span>PATTERN ANALYSIS</span>
                  <Activity className="w-3 h-3 text-amber-400 animate-pulse" />
                </div>
                
                {activeScenario === 'falling_behind' && (
                  <>
                    <div className="flex justify-between"><span>Distance Trend:</span><span className="text-amber-400">+142m increasing</span></div>
                    <div className="flex justify-between"><span>Sustained Time:</span><span className="text-white">35s &gt; threshold</span></div>
                    <div className="pt-1 text-[10px] text-white/50 border-t border-white/10 italic">
                      Sustained movement condition confirmed (reducing false alerts)
                    </div>
                  </>
                )}

                {activeScenario === 'route_deviation' && (
                  <>
                    <div className="flex justify-between"><span>Off-Route Distance:</span><span className="text-amber-400">85m off trail</span></div>
                    <div className="flex justify-between"><span>Vector Bearing:</span><span className="text-white">310° NW divergence</span></div>
                    <div className="pt-1 text-[10px] text-white/50 border-t border-white/10 italic">
                      Divergence from planned route detected
                    </div>
                  </>
                )}

                {activeScenario === 'unexpected_stop' && (
                  <>
                    <div className="flex justify-between"><span>Speed:</span><span className="text-red-400">0.0 km/h (Stationary)</span></div>
                    <div className="flex justify-between"><span>Group Distance:</span><span className="text-white">620m ahead</span></div>
                    <div className="pt-1 text-[10px] text-white/50 border-t border-white/10 italic">
                      Speed ≈ 0 + sustained time + group context
                    </div>
                  </>
                )}

                {activeScenario === 'connectivity_loss' && (
                  <>
                    <div className="flex justify-between"><span>GPS Heartbeat:</span><span className="text-amber-400">Missed (2m ago)</span></div>
                    <div className="flex justify-between"><span>Last Coordinates:</span><span className="text-white">Ridge Pass</span></div>
                    <div className="pt-1 text-[10px] text-white/50 border-t border-white/10 italic">
                      Telemetry drop flagged; last known location marked
                    </div>
                  </>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* 6. SMART ALERT NOTIFICATION (Refined minimal notification sliding in from bottom-right) */}
          <div className="relative z-20 flex justify-between items-end">
            <div className="text-[11px] font-mono text-white/40">
              Simulation Time: {elapsedSec.toFixed(1)}s
            </div>

            <AnimatePresence>
              {simPhase === 'triggered' && (
                <motion.div
                  initial={{ opacity: 0, x: 20, y: 10 }}
                  animate={{ opacity: 1, x: 0, y: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                  className="p-4 rounded-xl bg-[#090A0D]/95 border border-amber-500/40 text-left font-mono max-w-sm backdrop-blur-xl shadow-[0_10px_40px_rgba(0,0,0,0.9)]"
                >
                  <div className="flex items-center justify-between text-[10px] text-amber-400 tracking-wider font-bold uppercase mb-1">
                    <span className="flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {activeScenario === 'falling_behind' && 'FALLING BEHIND'}
                      {activeScenario === 'route_deviation' && 'ROUTE DEVIATION'}
                      {activeScenario === 'unexpected_stop' && 'UNEXPECTED STOP'}
                      {activeScenario === 'connectivity_loss' && 'CONNECTION LOST'}
                    </span>
                    <span className="text-white/40">Just now</span>
                  </div>

                  <p className="text-xs text-white/90 leading-snug mt-1 font-sans">
                    {activeScenario === 'falling_behind' && 'Keshav is moving away from the group (142m lag).'}
                    {activeScenario === 'route_deviation' && 'Priya departed from the planned trail onto side path.'}
                    {activeScenario === 'unexpected_stop' && 'Aditi has been stationary for 3m 40s while group progressed.'}
                    {activeScenario === 'connectivity_loss' && 'Rahul lost GPS signal. Last active near Ridge Pass.'}
                  </p>

                  <div className="mt-3 pt-2 border-t border-white/10 flex items-center justify-between text-[11px]">
                    <span className="text-white/50">Action required</span>
                    <Link
                      href="/create-group"
                      className="text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1 transition-colors"
                    >
                      View member <ChevronRight className="w-3 h-3" />
                    </Link>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

      </section>

      {/* 11. EXPLANATION SECTION (Large Editorial Statement & Visual Timeline — NO CARDS) */}
      <section className="py-24 px-6 max-w-4xl mx-auto text-center border-t border-white/5">
        <h2 className="text-3xl sm:text-5xl md:text-6xl font-medium tracking-tight text-white leading-tight">
          RALLY doesn&apos;t wait <br />
          <span className="font-serif italic font-normal text-white/85">
            for an emergency.
          </span>
        </h2>

        <p className="mt-6 text-base sm:text-lg text-white/60 max-w-xl mx-auto font-normal leading-relaxed">
          It watches movement continuously, looks for meaningful changes, and brings attention to situations that persist.
        </p>

        {/* Minimal Visual Timeline (Typography + Thin Lines, No Cards) */}
        <div className="mt-16 max-w-3xl mx-auto">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6 sm:gap-2 font-mono text-xs text-white/70">
            
            <div className="flex flex-col items-center">
              <div className="w-2.5 h-2.5 rounded-full bg-white/20 border border-white mb-2" />
              <span className="font-bold tracking-widest text-white uppercase">MOVEMENT</span>
              <span className="text-[10px] text-white/40 mt-0.5">Continuous GPS Ingestion</span>
            </div>

            <div className="h-8 sm:h-[1px] w-[1px] sm:w-20 bg-white/20" />

            <div className="flex flex-col items-center">
              <div className="w-2.5 h-2.5 rounded-full bg-white/20 border border-white mb-2" />
              <span className="font-bold tracking-widest text-white uppercase">PATTERN</span>
              <span className="text-[10px] text-white/40 mt-0.5">Sustained Trend Analysis</span>
            </div>

            <div className="h-8 sm:h-[1px] w-[1px] sm:w-20 bg-white/20" />

            <div className="flex flex-col items-center">
              <div className="w-2.5 h-2.5 rounded-full bg-amber-400 mb-2 shadow-[0_0_10px_rgba(245,158,11,0.8)]" />
              <span className="font-bold tracking-widest text-amber-400 uppercase">DETECTION</span>
              <span className="text-[10px] text-amber-400/60 mt-0.5">Anomaly Verification</span>
            </div>

            <div className="h-8 sm:h-[1px] w-[1px] sm:w-20 bg-white/20" />

            <div className="flex flex-col items-center">
              <div className="w-2.5 h-2.5 rounded-full bg-amber-400 mb-2 animate-ping" />
              <span className="font-bold tracking-widest text-white uppercase">ALERT</span>
              <span className="text-[10px] text-white/40 mt-0.5">Group Notification</span>
            </div>

          </div>
        </div>
      </section>

      {/* 14. FINAL SECTION (Cinematic CTA) */}
      <section className="pb-28 px-6 max-w-3xl mx-auto text-center">
        <div className="pt-16 border-t border-white/10 flex flex-col items-center">
          <h3 className="text-3xl sm:text-5xl font-medium text-white tracking-tight">
            Attention when it matters.
          </h3>

          <p className="mt-4 text-base text-white/60 font-normal">
            Stay focused on the journey. RALLY watches the movement.
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
