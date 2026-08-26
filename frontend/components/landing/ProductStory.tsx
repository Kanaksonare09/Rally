'use client';

import React from 'react';
import { motion } from 'framer-motion';

export default function ProductStory() {
  return (
    <section className="py-28 md:py-36 px-6 md:px-12 bg-background border-t border-white/10">
      <div className="max-w-5xl mx-auto space-y-16">
        
        {/* Section Header */}
        <div className="max-w-3xl space-y-4">
          <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
            THE PROBLEM WITH GROUPS IN MOTION
          </div>

          <h2 className="text-3xl md:text-5xl tracking-tight font-medium leading-[1.15] text-white">
            Moving together is harder <br />
            <span className="font-serif italic font-normal text-white/90">
              than it looks.
            </span>
          </h2>

          <p className="text-base sm:text-lg text-white/60 font-normal leading-relaxed max-w-xl pt-2">
            Plans change. People separate. Routes drift. RALLY keeps the entire group visible when the real journey starts.
          </p>
        </div>

        {/* 3-Stage Story Sequence */}
        <div className="relative pt-6">
          {/* Subtle Horizontal Connecting Line */}
          <div className="hidden md:block absolute top-[62px] left-12 right-12 h-[1px] bg-white/15 z-0" />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-10 relative z-10">
            
            {/* Stage 01 — PLAN */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-3">
                <span className="w-8 h-8 rounded-full bg-white/10 border border-white/20 font-mono text-xs text-white flex items-center justify-center font-bold">
                  01
                </span>
                <span className="font-mono text-xs font-bold text-white tracking-widest uppercase">
                  PLAN
                </span>
              </div>

              {/* Minimal Route Visual */}
              <div className="p-5 rounded-xl bg-[#08080A] border border-white/10 font-mono text-xs h-36 flex items-center justify-center">
                <svg className="w-full h-full" viewBox="0 0 200 80">
                  <path d="M 20 40 L 180 40" stroke="rgba(255,255,255,0.3)" strokeWidth="2" strokeDasharray="4 4" />
                  <circle cx="20" cy="40" r="4" fill="#38bdf8" />
                  <circle cx="180" cy="40" r="4" fill="#34d399" />
                  <text x="20" y="60" fill="rgba(255,255,255,0.5)" fontSize="9">START</text>
                  <text x="180" y="60" fill="rgba(255,255,255,0.5)" fontSize="9" textAnchor="end">DESTINATION</text>
                </svg>
              </div>

              <p className="text-xs sm:text-sm text-white/60 leading-relaxed font-normal">
                A simple route is planned. Everything looks straightforward on paper before departure.
              </p>
            </motion.div>

            {/* Stage 02 — MOVE */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: 0.15 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-3">
                <span className="w-8 h-8 rounded-full bg-white/10 border border-white/20 font-mono text-xs text-white flex items-center justify-center font-bold">
                  02
                </span>
                <span className="font-mono text-xs font-bold text-white tracking-widest uppercase">
                  MOVE
                </span>
              </div>

              {/* Animated Route Movement Visual */}
              <div className="p-5 rounded-xl bg-[#08080A] border border-white/10 font-mono text-xs h-36 flex items-center justify-center">
                <svg className="w-full h-full" viewBox="0 0 200 80">
                  <path d="M 20 40 Q 100 20 180 40" stroke="#22d3ee" strokeWidth="2" fill="none" />
                  <circle cx="60" cy="33" r="3.5" fill="#ffffff" />
                  <circle cx="100" cy="30" r="3.5" fill="#38bdf8" />
                  <circle cx="140" cy="33" r="3.5" fill="#34d399" />
                </svg>
              </div>

              <p className="text-xs sm:text-sm text-white/60 leading-relaxed font-normal">
                Real movement begins. Traffic, pace differences, and terrain start stretching the group.
              </p>
            </motion.div>

            {/* Stage 03 — RESPOND */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-3">
                <span className="w-8 h-8 rounded-full bg-amber-500/20 border border-amber-500/40 font-mono text-xs text-amber-400 flex items-center justify-center font-bold">
                  03
                </span>
                <span className="font-mono text-xs font-bold text-amber-400 tracking-widest uppercase">
                  RESPOND
                </span>
              </div>

              {/* Alert & Drift Visual */}
              <div className="p-5 rounded-xl bg-[#08080A] border border-white/10 font-mono text-xs h-36 flex items-center justify-center">
                <svg className="w-full h-full" viewBox="0 0 200 80">
                  <path d="M 20 40 Q 100 20 180 40" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" fill="none" />
                  <path d="M 80 30 Q 110 65 140 60" stroke="#fbbf24" strokeWidth="1.5" strokeDasharray="3 3" fill="none" />
                  <circle cx="140" cy="60" r="4" fill="#fbbf24" className="animate-ping" />
                  <circle cx="140" cy="60" r="3.5" fill="#fbbf24" />
                  <text x="140" y="75" fill="#fbbf24" fontSize="8" textAnchor="middle">GAP DETECTED</text>
                </svg>
              </div>

              <p className="text-xs sm:text-sm text-white/60 leading-relaxed font-normal">
                One member drifts away. RALLY immediately notices and surfaces the issue before anyone gets lost.
              </p>
            </motion.div>

          </div>
        </div>

      </div>
    </section>
  );
}
