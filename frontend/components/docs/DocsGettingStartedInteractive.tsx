'use client';

import React, { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { 
  BookOpen, 
  ChevronDown, 
  Shield, 
  Users, 
  Compass, 
  Radio, 
  ArrowRight,
  CheckCircle2,
  Lock,
  Key
} from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

interface DocSection {
  id: string;
  num: string;
  title: string;
}

const DOC_SECTIONS: DocSection[] = [
  { id: 'getting-started', num: '01', title: 'Getting started' },
  { id: 'creating-a-rally', num: '02', title: 'Creating a Rally' },
  { id: 'joining-a-rally', num: '03', title: 'Joining a Rally' },
  { id: 'trips', num: '04', title: 'Starting and ending a trip' },
  { id: 'tracking', num: '05', title: 'Live tracking & alerts' },
  { id: 'safety', num: '06', title: 'Safety & SOS' },
];

export default function DocsGettingStartedInteractive() {
  const [activeSectionId, setActiveSectionId] = useState<string>('getting-started');
  const [scrollProgress, setScrollProgress] = useState<number>(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  // Track scroll position for reading progress bar and TOC active link highlighting
  useEffect(() => {
    const handleScroll = () => {
      const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (totalHeight > 0) {
        setScrollProgress(Math.min(1, Math.max(0, window.scrollY / totalHeight)));
      }

      // Detect active section based on scroll position
      const scrollPos = window.scrollY + 200;
      for (let i = DOC_SECTIONS.length - 1; i >= 0; i--) {
        const sec = document.getElementById(DOC_SECTIONS[i].id);
        if (sec && sec.offsetTop <= scrollPos) {
          setActiveSectionId(DOC_SECTIONS[i].id);
          break;
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      const top = el.getBoundingClientRect().top + window.scrollY - 100;
      window.scrollTo({ top, behavior: 'smooth' });
    }
    setMobileMenuOpen(false);
  };

  const activeSectionObj = DOC_SECTIONS.find((s) => s.id === activeSectionId) || DOC_SECTIONS[0];

  return (
    <div className="bg-[#000000] text-white min-h-screen font-sans selection:bg-white/20 selection:text-white">
      {/* Subtle 1px Reading Progress Indicator Line at top */}
      <div 
        className="fixed top-0 left-0 h-[2px] bg-white z-50 transition-all duration-75"
        style={{ width: `${scrollProgress * 100}%` }}
      />

      {/* Global Navbar */}
      <Navbar />

      {/* 3. HERO SECTION (~35–45vh) */}
      <section className="pt-20 pb-12 px-6 max-w-5xl mx-auto text-center flex flex-col items-center border-b border-white/10">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono tracking-[0.2em] text-white/70 uppercase mb-6"
        >
          <BookOpen className="w-3 h-3 text-white/70" />
          DOCUMENTATION
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-5xl md:text-6xl font-medium tracking-tight text-white max-w-3xl leading-[1.1]"
        >
          Learn how <br />
          <span className="font-serif italic font-normal text-white/90 tracking-normal">
            RALLY works.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-4 text-base sm:text-lg text-white/60 max-w-2xl font-normal leading-relaxed mx-auto"
        >
          A quick guide to creating a group, running a trip, and keeping your group visible to each other.
        </motion.p>
      </section>

      {/* Mobile Sticky Table of Contents Dropdown (< 768px) */}
      <div className="md:hidden sticky top-16 z-40 bg-[#000000]/95 backdrop-blur-md border-b border-white/10 px-6 py-3 font-mono text-xs">
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="w-full flex items-center justify-between text-white/70 py-1"
        >
          <span className="flex items-center gap-2">
            <span className="text-white/40 uppercase">ON THIS PAGE:</span>
            <span className="text-white font-bold">{activeSectionObj.title}</span>
          </span>
          <ChevronDown className={`w-4 h-4 transition-transform ${mobileMenuOpen ? 'rotate-180' : ''}`} />
        </button>

        {mobileMenuOpen && (
          <div className="mt-3 pt-3 border-t border-white/10 space-y-2">
            {DOC_SECTIONS.map((sec) => (
              <button
                key={sec.id}
                onClick={() => scrollTo(sec.id)}
                className={`w-full text-left py-1.5 px-2 rounded flex items-center gap-3 transition-colors ${
                  activeSectionId === sec.id ? 'bg-white/10 text-white font-bold' : 'text-white/50 hover:text-white'
                }`}
              >
                <span className="text-[10px] text-white/40">{sec.num}</span>
                <span>{sec.title}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 4. MAIN DOCUMENTATION 3-COLUMN STRUCTURE (20% / 55% / 25%) */}
      <div className="max-w-[1280px] mx-auto px-6 py-16 flex flex-col md:flex-row gap-12 lg:gap-16">
        
        {/* 5. LEFT STICKY TABLE OF CONTENTS (20% Desktop) */}
        <aside className="hidden md:block w-1/5 shrink-0">
          <div className="sticky top-28 font-mono text-xs space-y-6">
            <div className="text-[10px] text-white/40 uppercase tracking-[0.2em]">
              ON THIS PAGE
            </div>

            <nav className="space-y-3" aria-label="Table of contents">
              {DOC_SECTIONS.map((sec) => {
                const isActive = activeSectionId === sec.id;
                return (
                  <button
                    key={sec.id}
                    onClick={() => scrollTo(sec.id)}
                    className={`group w-full text-left flex items-center gap-3 py-1 transition-all duration-200 ${
                      isActive ? 'text-white font-semibold' : 'text-white/40 hover:text-white/80'
                    }`}
                  >
                    {/* Active vertical line indicator */}
                    <span 
                      className={`w-[2px] h-4 rounded-full transition-all ${
                        isActive ? 'bg-white scale-y-100' : 'bg-transparent scale-y-0'
                      }`} 
                    />
                    <span className="text-[10px] opacity-50">{sec.num}</span>
                    <span className="truncate">{sec.title}</span>
                  </button>
                );
              })}
            </nav>
          </div>
        </aside>

        {/* 6. CENTER MAIN DOCUMENTATION READING COLUMN (55% Desktop, 600-700px width) */}
        <main className="w-full md:w-[55%] max-w-[700px] space-y-24">
          
          {/* SECTION 01 — GETTING STARTED */}
          <section id="getting-started" className="scroll-mt-28 space-y-6">
            <div className="font-mono text-xs text-white/40 tracking-[0.2em]">01</div>
            
            <h2 className="text-2xl sm:text-3xl font-medium text-white tracking-tight">
              Getting started
            </h2>

            <div className="text-base text-white/70 leading-[1.8] space-y-6 font-normal">
              <p>
                Create an account, then either start a new group or join one with a code from your group's leader. Every group needs at least one leader — whoever creates the group becomes its leader automatically.
              </p>

              {/* Inline Step Callout */}
              <div className="pt-2 border-l border-white/20 pl-4 space-y-2">
                <div className="font-mono text-xs text-white uppercase tracking-wider font-bold">
                  CREATE AN ACCOUNT
                </div>
                <p className="text-sm text-white/60">
                  Account setup takes under a minute. You can immediately generate your first Rally or accept an invite code.
                </p>
              </div>

              <div className="border-l border-white/20 pl-4 space-y-2">
                <div className="font-mono text-xs text-white uppercase tracking-wider font-bold">
                  GROUP LEADER
                </div>
                <p className="text-sm text-white/60">
                  Leadership can be handed off to another active member at any time, and a leader can remove a member from the group if needed.
                </p>
              </div>

              {/* Editorial Callout Note (Item #13) */}
              <div className="mt-6 p-4 rounded bg-white/[0.03] border-l-2 border-white/40 text-xs font-mono space-y-1">
                <div className="text-white font-bold uppercase tracking-wider">NOTE</div>
                <div className="text-white/60 font-sans text-sm">
                  Only active members of the specific group can see its location and trip data.
                </div>
              </div>
            </div>
          </section>

          <hr className="border-white/10" />

          {/* SECTION 02 — CREATING A RALLY */}
          <section id="creating-a-rally" className="scroll-mt-28 space-y-6">
            <div className="font-mono text-xs text-white/40 tracking-[0.2em]">02</div>

            <h2 className="text-2xl sm:text-3xl font-medium text-white tracking-tight">
              Creating a Rally
            </h2>

            <div className="text-base text-white/70 leading-[1.8] space-y-6 font-normal">
              <p>
                From <Link href="/create-group" className="text-white underline underline-offset-4 hover:text-white/80">Create Rally</Link>, give your group a name and, optionally, a destination. RALLY generates a short join code you can share with the rest of your group — anyone with the code can join while the group is active.
              </p>

              {/* Visual Numbered Process (Vertical Timeline, NOT Cards) - Item #8 */}
              <div className="mt-8 font-mono text-xs space-y-6 border-l border-white/10 pl-6 relative">
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-2.5 h-2.5 rounded-full bg-white" />
                  <div className="text-white font-bold uppercase tracking-wider">01 — CREATE A RALLY</div>
                  <div className="text-white/60 font-sans text-sm mt-1">Define group name & optional trip destination.</div>
                </div>

                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-2.5 h-2.5 rounded-full bg-white/40" />
                  <div className="text-white font-bold uppercase tracking-wider">02 — SET YOUR GROUP UP</div>
                  <div className="text-white/60 font-sans text-sm mt-1">Automatic leader assignment & safety parameters.</div>
                </div>

                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-2.5 h-2.5 rounded-full bg-white/40" />
                  <div className="text-white font-bold uppercase tracking-wider">03 — INVITE YOUR GROUP</div>
                  <div className="text-white/60 font-sans text-sm mt-1">
                    Share the unique 6-character code <code className="px-1.5 py-0.5 rounded bg-white/10 text-white font-mono border border-white/20">RALLY-7K2P</code>.
                  </div>
                </div>

                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-2.5 h-2.5 rounded-full bg-white/40" />
                  <div className="text-white font-bold uppercase tracking-wider">04 — START MOVING</div>
                  <div className="text-white/60 font-sans text-sm mt-1">Members connect to live stream automatically upon joining.</div>
                </div>
              </div>
            </div>
          </section>

          <hr className="border-white/10" />

          {/* SECTION 03 — JOINING A RALLY */}
          <section id="joining-a-rally" className="scroll-mt-28 space-y-6">
            <div className="font-mono text-xs text-white/40 tracking-[0.2em]">03</div>

            <h2 className="text-2xl sm:text-3xl font-medium text-white tracking-tight">
              Joining a Rally
            </h2>

            <div className="text-base text-white/70 leading-[1.8] space-y-6 font-normal">
              <p>
                Have a code from your group's leader? Head to{' '}
                <Link href="/join-group" className="text-white underline underline-offset-4 hover:text-white/80">Join a Rally</Link>{' '}
                and enter it. You'll appear on the group's live map as soon as you join.
              </p>

              {/* Minimal Abstract Process Flow (Item #9) */}
              <div className="p-6 rounded-xl bg-white/[0.02] border border-white/10 font-mono text-xs flex flex-col sm:flex-row items-center justify-between gap-4 text-white/70">
                <div className="flex items-center gap-2">
                  <Key className="w-4 h-4 text-white/50" />
                  <span className="px-2 py-1 rounded bg-white/10 text-white font-bold">RALLY CODE</span>
                </div>

                <ArrowRight className="w-4 h-4 text-white/30 hidden sm:block" />

                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-white/50" />
                  <span className="text-white font-bold">JOIN</span>
                </div>

                <ArrowRight className="w-4 h-4 text-white/30 hidden sm:block" />

                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-emerald-400 font-bold">YOUR GROUP</span>
                </div>
              </div>
            </div>
          </section>

          <hr className="border-white/10" />

          {/* SECTION 04 — STARTING AND ENDING A TRIP */}
          <section id="trips" className="scroll-mt-28 space-y-6">
            <div className="font-mono text-xs text-white/40 tracking-[0.2em]">04</div>

            <h2 className="text-2xl sm:text-3xl font-medium text-white tracking-tight">
              Starting and ending a trip
            </h2>

            <div className="text-base text-white/70 leading-[1.8] space-y-6 font-normal">
              <p>
                A trip belongs to a group and moves through a simple lifecycle: created, then active, then completed — or cancelled before it ever starts. A group can only have one active trip running at a time.
              </p>

              {/* Horizontal Lifecycle Timeline (Item #10) */}
              <div className="p-6 rounded-xl bg-white/[0.02] border border-white/10 font-mono text-xs">
                <div className="text-[10px] text-white/40 uppercase tracking-widest mb-4">TRIP LIFECYCLE STAGES</div>

                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-white">
                  <div className="text-center">
                    <span className="block font-bold">START</span>
                    <span className="text-[10px] text-white/40">Creation & Setup</span>
                  </div>

                  <div className="hidden sm:block flex-1 h-[1px] bg-white/20 mx-4" />

                  <div className="text-center">
                    <span className="block font-bold text-emerald-400">ACTIVE</span>
                    <span className="text-[10px] text-emerald-400/60">Live Location Stream</span>
                  </div>

                  <div className="hidden sm:block flex-1 h-[1px] bg-white/20 mx-4" />

                  <div className="text-center">
                    <span className="block font-bold">COMPLETE</span>
                    <span className="text-[10px] text-white/40">Saved to Archive</span>
                  </div>
                </div>
              </div>

              <p>
                Any active member can create and start a trip. Ending a trip closes it out normally; cancelling is only available before a trip has started, and can be done by whoever created it or by the group leader. Completed and cancelled trips remain preserved in history.
              </p>
            </div>
          </section>

          <hr className="border-white/10" />

          {/* SECTION 05 — LIVE TRACKING & ALERTS */}
          <section id="tracking" className="scroll-mt-28 space-y-6">
            <div className="font-mono text-xs text-white/40 tracking-[0.2em]">05</div>

            <h2 className="text-2xl sm:text-3xl font-medium text-white tracking-tight">
              Live tracking & alerts
            </h2>

            <div className="text-base text-white/70 leading-[1.8] space-y-6 font-normal">
              <p>
                Once a trip is active, each member's position updates on the shared map in real time. RALLY watches for members falling behind, drifting from the group, or losing connectivity, and surfaces it as soon as it happens rather than after the fact.
              </p>

              {/* Abstract Functional Diagram (Item #11) */}
              <div className="p-6 rounded-xl bg-white/[0.02] border border-white/10 font-mono text-xs flex flex-wrap items-center justify-between gap-4 text-white/70">
                <span>MEMBER</span>
                <span className="text-white/30">↓</span>
                <span>LOCATION</span>
                <span className="text-white/30">↓</span>
                <span>GROUP</span>
                <span className="text-white/30">↓</span>
                <span className="text-emerald-400 font-bold">ALERT</span>
              </div>
            </div>
          </section>

          <hr className="border-white/10" />

          {/* SECTION 06 — SAFETY & SOS */}
          <section id="safety" className="scroll-mt-28 space-y-6">
            <div className="font-mono text-xs text-white/40 tracking-[0.2em]">06</div>

            <div className="flex items-center gap-3">
              <span className="px-2 py-0.5 rounded bg-white/10 text-white font-mono text-[10px] font-bold uppercase tracking-widest border border-white/20">SAFETY</span>
              <h2 className="text-2xl sm:text-3xl font-medium text-white tracking-tight">
                Safety & SOS
              </h2>
            </div>

            <div className="text-base text-white/70 leading-[1.8] space-y-6 font-normal">
              <p>
                Location data is only ever visible to active members of the same group and trip. If something goes wrong, a single tap on SOS shares your exact location with the group immediately.
              </p>

              <div className="p-4 rounded bg-white/[0.03] border-l-2 border-white/40 text-xs font-mono space-y-1">
                <div className="text-white font-bold uppercase tracking-wider flex items-center gap-2">
                  <Lock className="w-3.5 h-3.5 text-white/60" /> PRIVACY & DATA ISOLATION
                </div>
                <div className="text-white/60 font-sans text-sm">
                  Trip data is isolated to active group members and automatically purged from active memory when a trip concludes. See the{' '}
                  <Link href="/safety" className="text-white underline underline-offset-4 hover:text-white/80">Safety</Link>{' '}
                  page for complete architectural details.
                </div>
              </div>
            </div>
          </section>

        </main>

        {/* 16. RIGHT SIDE CONTEXTUAL PANEL (25% Desktop) */}
        <aside className="hidden lg:block w-1/4 shrink-0">
          <div className="sticky top-28 font-mono text-xs space-y-6 p-6 rounded-2xl bg-white/[0.02] border border-white/10">
            <div className="text-[10px] text-white/40 uppercase tracking-[0.2em]">
              RALLY BASICS
            </div>

            <div className="space-y-4">
              <div>
                <div className="text-white/40 text-[10px]">TOTAL SECTIONS</div>
                <div className="text-white font-bold text-sm">6 Sections</div>
              </div>

              <div>
                <div className="text-white/40 text-[10px]">ESTIMATED READ</div>
                <div className="text-white font-bold text-sm">~4 min read</div>
              </div>

              <hr className="border-white/10" />

              <div>
                <div className="text-white/40 text-[10px] uppercase">YOU ARE READING</div>
                <div className="text-white font-semibold text-xs mt-1 truncate">
                  {activeSectionObj.title}
                </div>
              </div>
            </div>
          </div>
        </aside>

      </div>

      {/* Footer */}
      <Footer />
    </div>
  );
}
