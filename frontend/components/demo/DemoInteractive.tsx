'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { PlayCircle, Play, Pause, RotateCcw, MapPin, Users, AlertTriangle, Activity, Navigation, Clock } from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

type TabType = 'overview' | 'live' | 'trip' | 'alerts' | 'members' | 'history';

interface DemoMember {
  id: string;
  name: string;
  status: 'MOVING' | 'STOPPED' | 'NEAR GROUP';
  distance: string;
  cx: number;
  cy: number;
}

const DEMO_MEMBERS: DemoMember[] = [
  { id: 'm1', name: 'Alex (Leader)', status: 'MOVING', distance: '5.2 km', cx: 120, cy: 180 },
  { id: 'm2', name: 'Sam', status: 'MOVING', distance: '5.1 km', cx: 180, cy: 160 },
  { id: 'm3', name: 'Jordan', status: 'STOPPED', distance: '4.8 km', cx: 280, cy: 220 },
  { id: 'm4', name: 'Maya', status: 'NEAR GROUP', distance: '5.0 km', cx: 380, cy: 150 },
];

const DEMO_ALERTS = [
  { time: '10:42', text: 'Alex moved off route', type: 'warning' },
  { time: '10:45', text: 'Group reunited', type: 'success' },
  { time: '10:51', text: 'Connectivity restored for Jordan', type: 'info' },
];

export default function DemoInteractive() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(35); // 0 to 100%
  const [selectedMember, setSelectedMember] = useState<DemoMember | null>(null);
  const [hoveredStep, setHoveredStep] = useState<number | null>(null);

  const animationRef = useRef<number | null>(null);

  // Simulation timer when isPlaying is true
  useEffect(() => {
    if (isPlaying) {
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 100) {
            setIsPlaying(false);
            return 100;
          }
          return prev + 1;
        });
      }, 100);
      return () => clearInterval(interval);
    }
  }, [isPlaying]);

  const handlePlayPause = () => {
    if (progress >= 100) setProgress(0);
    setIsPlaying(!isPlaying);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setProgress(0);
  };

  return (
    <div className="bg-[#000000] text-white min-h-screen font-sans selection:bg-white/20 selection:text-white">
      {/* Global Navbar */}
      <Navbar />

      {/* 2. HERO SECTION (~32–38vh) */}
      <section className="pt-20 pb-8 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono tracking-[0.2em] text-white/70 uppercase mb-6"
        >
          <PlayCircle className="w-3.5 h-3.5 text-white/70" />
          DEMO
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl font-medium tracking-tight text-white max-w-3xl leading-[1.08]"
        >
          See RALLY <br />
          <span className="font-serif italic font-normal text-white/90 tracking-normal">
            before you create one.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-4 text-base sm:text-lg text-white/60 max-w-xl font-normal leading-relaxed"
        >
          This is a live preview of what your group sees once a trip is running — no login required.
        </motion.p>
      </section>

      {/* 3, 4, 5. INTERACTIVE PRODUCT PREVIEW APPLICATION WINDOW */}
      <section className="px-6 py-8 max-w-[1100px] mx-auto">
        <div className="flex items-center justify-between font-mono text-[10px] text-white/40 uppercase tracking-widest mb-3">
          <span>INTERACTIVE PREVIEW</span>
          <span>SAMPLE TRIP DATA</span>
        </div>

        {/* BROWSER / APP FRAME */}
        <div className="rounded-xl bg-[#0A0A0B] border border-white/15 overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.8)]">
          
          {/* Top Window Bar */}
          <div className="px-4 py-3 bg-[#101011] border-b border-white/10 flex items-center justify-between font-mono text-xs text-white/60">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-white/20" />
              <span className="w-2.5 h-2.5 rounded-full bg-white/20" />
              <span className="w-2.5 h-2.5 rounded-full bg-white/20" />
            </div>

            <div className="text-[11px] tracking-wider text-white font-semibold">
              RALLY TRIP — PACIFIC COAST EXPEDITION
            </div>

            <div className="flex items-center gap-2 text-emerald-400 text-[10px] font-bold">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              LIVE
            </div>
          </div>

          {/* APP BODY (Sidebar + Content area) */}
          <div className="flex flex-col md:flex-row min-h-[460px] md:min-h-[500px]">
            
            {/* 5. DEMO SIDEBAR (Horizontally scrollable on mobile) */}
            <nav 
              className="w-full md:w-52 bg-[#0d0d0e] border-b md:border-b-0 md:border-r border-white/10 p-2 md:p-4 flex md:flex-col gap-1 overflow-x-auto font-mono text-xs text-white/50 shrink-0"
              aria-label="Demo Navigation"
            >
              {[
                { id: 'overview', label: 'Overview', icon: Activity },
                { id: 'live', label: 'Live Group', icon: Users },
                { id: 'trip', label: 'Trip', icon: Navigation },
                { id: 'alerts', label: 'Alerts', icon: AlertTriangle },
                { id: 'members', label: 'Members', icon: MapPin },
                { id: 'history', label: 'History', icon: Clock },
              ].map((tab) => {
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as TabType)}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-md whitespace-nowrap transition-all text-left ${
                      isActive
                        ? 'bg-white/10 text-white font-semibold'
                        : 'hover:bg-white/5 hover:text-white'
                    }`}
                  >
                    <tab.icon className="w-3.5 h-3.5 text-white/60" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </nav>

            {/* MAIN DEMO DISPLAY AREA */}
            <div className="flex-1 p-6 flex flex-col justify-between relative bg-[#060607]">
              
              {/* TAB 1: OVERVIEW */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* 6. OVERVIEW DASHBOARD READOUTS */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-xs">
                    <div className="p-3.5 rounded-lg bg-white/[0.03] border border-white/10 space-y-1">
                      <div className="text-[10px] text-white/40 uppercase">GROUP HEALTH</div>
                      <div className="text-xl font-bold text-emerald-400">98%</div>
                    </div>
                    <div className="p-3.5 rounded-lg bg-white/[0.03] border border-white/10 space-y-1">
                      <div className="text-[10px] text-white/40 uppercase">MEMBERS</div>
                      <div className="text-xl font-bold text-white">8 / 8</div>
                    </div>
                    <div className="p-3.5 rounded-lg bg-white/[0.03] border border-white/10 space-y-1">
                      <div className="text-[10px] text-white/40 uppercase">DISTANCE</div>
                      <div className="text-xl font-bold text-white">{(5.2 * (progress / 100)).toFixed(1)} km</div>
                    </div>
                    <div className="p-3.5 rounded-lg bg-white/[0.03] border border-white/10 space-y-1">
                      <div className="text-[10px] text-white/40 uppercase">RISK</div>
                      <div className="text-xl font-bold text-white">LOW</div>
                    </div>
                  </div>

                  {/* 7 & 8. STYLIZED SVG INTERACTIVE MAP */}
                  <div className="relative w-full h-[260px] bg-[#030303] rounded-xl border border-white/10 overflow-hidden flex items-center justify-center">
                    <svg className="w-full h-full" viewBox="0 0 600 300">
                      {/* Dark terrain grid lines */}
                      <line x1="0" y1="75" x2="600" y2="75" stroke="rgba(255,255,255,0.04)" />
                      <line x1="0" y1="150" x2="600" y2="150" stroke="rgba(255,255,255,0.04)" />
                      <line x1="0" y1="225" x2="600" y2="225" stroke="rgba(255,255,255,0.04)" />

                      {/* Planned Route Line */}
                      <path
                        d="M 50 200 C 150 100, 300 250, 550 100"
                        fill="none"
                        stroke="rgba(255,255,255,0.15)"
                        strokeWidth="3"
                        strokeDasharray="4 4"
                      />

                      {/* Active Progress Path Line */}
                      <path
                        d="M 50 200 C 150 100, 300 250, 550 100"
                        fill="none"
                        stroke="#ffffff"
                        strokeWidth="3"
                        strokeDasharray="600"
                        strokeDashoffset={600 - (600 * progress) / 100}
                        className="transition-all duration-150"
                      />

                      {/* Start Point */}
                      <circle cx="50" cy="200" r="5" fill="#ffffff" />
                      <text x="50" y="225" fill="rgba(255,255,255,0.4)" fontSize="10" fontFamily="monospace" textAnchor="middle">
                        START
                      </text>

                      {/* Destination Point */}
                      <circle cx="550" cy="100" r="5" fill="#ffffff" />
                      <text x="550" y="125" fill="rgba(255,255,255,0.4)" fontSize="10" fontFamily="monospace" textAnchor="middle">
                        DESTINATION
                      </text>

                      {/* 9. Interactive Member Markers */}
                      {DEMO_MEMBERS.map((member, idx) => {
                        const currentX = member.cx + (progress * 2);
                        const isSelected = selectedMember?.id === member.id;
                        return (
                          <g key={member.id} className="cursor-pointer" onClick={() => setSelectedMember(member)}>
                            <circle cx={currentX} cy={member.cy} r="12" fill="rgba(255,255,255,0.1)" />
                            <circle cx={currentX} cy={member.cy} r="5" fill={isSelected ? '#10b981' : '#ffffff'} />
                            <text x={currentX} y={member.cy - 12} fill="white" fontSize="9" fontFamily="sans-serif" textAnchor="middle">
                              {member.name.split(' ')[0]}
                            </text>
                          </g>
                        );
                      })}
                    </svg>

                    {/* Member Info Popup Overlay */}
                    {selectedMember && (
                      <div className="absolute bottom-4 left-4 p-3 rounded-lg bg-[#0e0e10] border border-white/20 font-mono text-xs space-y-1 z-10 shadow-lg">
                        <div className="text-white font-bold">{selectedMember.name}</div>
                        <div className="text-emerald-400 text-[10px]">{selectedMember.status}</div>
                        <div className="text-white/50 text-[10px]">Distance: {selectedMember.distance}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 2: LIVE GROUP */}
              {activeTab === 'live' && (
                <div className="space-y-4 font-mono text-xs">
                  <div className="text-white font-bold text-sm tracking-wider uppercase">8 MEMBERS ACTIVE ON MAP</div>
                  <div className="space-y-2">
                    {DEMO_MEMBERS.map((m) => (
                      <div key={m.id} className="p-3 rounded bg-white/[0.03] border border-white/10 flex items-center justify-between">
                        <span className="text-white font-medium">{m.name}</span>
                        <span className="text-emerald-400 font-bold text-[10px]">{m.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 3: TRIP */}
              {activeTab === 'trip' && (
                <div className="space-y-6 font-mono text-xs">
                  <div className="text-white font-bold text-sm uppercase">PACIFIC COAST JOURNEY</div>
                  <div className="p-4 rounded-lg bg-white/[0.03] border border-white/10 space-y-4">
                    <div className="flex justify-between text-white/60">
                      <span>START: Monterey</span>
                      <span>DESTINATION: Big Sur</span>
                    </div>
                    <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                      <div className="bg-white h-full transition-all duration-300" style={{ width: `${progress}%` }} />
                    </div>
                    <div className="flex justify-between text-white font-bold">
                      <span>PROGRESS: {progress}%</span>
                      <span>EST. REMAINING: {Math.max(0, Math.round(45 * (1 - progress / 100)))} MINS</span>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: ALERTS */}
              {activeTab === 'alerts' && (
                <div className="space-y-4 font-mono text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-white font-bold text-sm uppercase">TELEMETRY EVENT TIMELINE</span>
                    <span className="px-2 py-0.5 rounded bg-white/10 text-white/50 text-[10px]">DEMO DATA</span>
                  </div>
                  <div className="space-y-2">
                    {DEMO_ALERTS.map((a, i) => (
                      <div key={i} className="p-3 rounded bg-white/[0.03] border border-white/10 flex items-center gap-4">
                        <span className="text-white/40">{a.time}</span>
                        <span className="text-white">{a.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 5: MEMBERS */}
              {activeTab === 'members' && (
                <div className="space-y-3 font-mono text-xs">
                  <div className="text-white font-bold text-sm uppercase">GROUP ROSTER</div>
                  <div className="divide-y divide-white/10">
                    {DEMO_MEMBERS.map((m) => (
                      <div key={m.id} className="py-2.5 flex items-center justify-between">
                        <span className="text-white">{m.name}</span>
                        <span className="text-white/50">{m.distance}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 6: HISTORY */}
              {activeTab === 'history' && (
                <div className="space-y-4 font-mono text-xs">
                  <div className="text-white font-bold text-sm uppercase">CHRONOLOGICAL EVENT LOG</div>
                  <ol className="space-y-3 text-white/70 border-l border-white/20 pl-4">
                    <li>09:30 AM — TRIP STARTED</li>
                    <li>09:32 AM — GROUP FORMED (8 MEMBERS)</li>
                    <li>10:15 AM — ROUTE DEVIATION DETECTED</li>
                    <li>10:45 AM — REJOINED MAIN ROUTE</li>
                  </ol>
                </div>
              )}

              {/* 16. DEMO CONTROLS BAR */}
              <div className="pt-4 border-t border-white/10 flex items-center justify-between font-mono text-xs">
                <div className="flex items-center gap-3">
                  <button
                    onClick={handlePlayPause}
                    className="px-4 py-2 rounded-full bg-white text-black font-semibold flex items-center gap-2 hover:bg-white/90 transition-all text-xs"
                  >
                    {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                    <span>{isPlaying ? 'PAUSE DEMO' : 'PLAY DEMO'}</span>
                  </button>

                  <button
                    onClick={handleReset}
                    className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-all"
                    title="Reset Demo"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="text-white/50 text-[11px]">
                  PROGRESS: <span className="text-white font-bold">{progress}%</span>
                </div>
              </div>

            </div>
          </div>
        </div>

        {/* 17. DEMO TIMELINE BELOW PREVIEW WINDOW */}
        <div className="mt-4 p-4 rounded-xl bg-[#080809] border border-white/10 font-mono text-xs text-white/50 flex items-center justify-between">
          <span className={progress >= 0 ? 'text-white font-bold' : ''}>START</span>
          <span className="h-[1px] flex-1 bg-white/20 mx-3" />
          <span className={progress >= 30 ? 'text-white font-bold' : ''}>GROUP FORMED</span>
          <span className="h-[1px] flex-1 bg-white/20 mx-3" />
          <span className={progress >= 60 ? 'text-white font-bold' : ''}>MOVING</span>
          <span className="h-[1px] flex-1 bg-white/20 mx-3" />
          <span className={progress >= 100 ? 'text-white font-bold' : ''}>ARRIVED</span>
        </div>
      </section>

      {/* 18 & 19. "FROM ZERO TO TRACKED" 4-STEP EXPLANATION */}
      <section className="py-20 max-w-[1100px] mx-auto px-6 border-t border-white/10">
        <div className="text-xs font-mono text-white/40 uppercase tracking-[0.2em] mb-4">
          HOW IT WORKS
        </div>

        <h2 className="text-3xl sm:text-4xl font-medium tracking-tight text-white mb-12">
          From zero to tracked, in four steps.
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 font-mono text-xs">
          {[
            { num: '01', title: 'CREATE A RALLY', desc: 'Create your group and set up the trip.', targetTab: 'overview' },
            { num: '02', title: 'BRING YOUR GROUP IN', desc: 'Share the invite code with everyone.', targetTab: 'members' },
            { num: '03', title: 'START THE TRIP', desc: 'Members join and location sharing begins.', targetTab: 'live' },
            { num: '04', title: 'WATCH IT TOGETHER', desc: 'See members, route, alerts, and trip progress.', targetTab: 'overview' },
          ].map((step, idx) => (
            <div
              key={step.num}
              onMouseEnter={() => {
                setHoveredStep(idx + 1);
                setActiveTab(step.targetTab as TabType);
              }}
              onMouseLeave={() => setHoveredStep(null)}
              className="space-y-3 cursor-pointer group p-4 rounded-xl border border-white/10 hover:border-white/30 transition-all bg-white/[0.01]"
            >
              <div className="text-white/40 group-hover:text-white font-bold transition-colors">
                {step.num}
              </div>
              <div className="text-white font-bold text-sm font-sans tracking-wide">
                {step.title}
              </div>
              <p className="text-white/50 font-sans text-xs leading-relaxed font-normal">
                {step.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* 22. COMPACT FINAL CTA */}
      <section className="pb-28 px-6 max-w-3xl mx-auto text-center border-t border-white/10 pt-16">
        <h3 className="text-3xl sm:text-5xl font-medium text-white tracking-tight">
          Start your next <br />
          <span className="font-serif italic font-normal text-white/90">
            journey together.
          </span>
        </h3>

        <p className="mt-4 text-base text-white/60 font-normal font-sans">
          Create a Rally in seconds, or join one with a code from your group leader.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-4 font-mono text-xs">
          <Link
            href="/register"
            className="px-8 py-3.5 rounded-full bg-white text-black hover:bg-white/90 transition-colors uppercase tracking-wider font-semibold shadow-[0_0_30px_rgba(255,255,255,0.2)]"
          >
            Get Started for Free
          </Link>

          <Link
            href="/join-group"
            className="px-8 py-3.5 rounded-full border border-white/20 text-white hover:bg-white/10 transition-colors uppercase tracking-wider font-semibold"
          >
            Join a Rally
          </Link>
        </div>
      </section>

      {/* Footer */}
      <Footer />
    </div>
  );
}
