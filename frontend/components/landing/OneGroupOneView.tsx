'use client';

import React from 'react';
import { motion } from 'framer-motion';

export default function OneGroupOneView() {
  return (
    <section className="py-28 md:py-36 px-6 md:px-12 bg-background border-t border-white/10">
      <div className="max-w-5xl mx-auto space-y-16">
        
        {/* Header */}
        <div className="max-w-3xl space-y-4">
          <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
            THE SINGLE SOURCE OF TRUTH
          </div>

          <h2 className="text-3xl md:text-5xl md:text-6xl tracking-tight font-medium leading-[1.08] text-white">
            One group. <br />
            <span className="font-serif italic font-normal text-white/95">
              One shared view.
            </span>
          </h2>

          <p className="text-base sm:text-lg text-white/60 font-normal leading-relaxed max-w-xl pt-2">
            Instead of checking six phones, six locations, and six different versions of the plan, RALLY turns movement into one clear picture.
          </p>
        </div>

        {/* Minimal Typographic Comparison (No Cards) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 pt-8 border-t border-white/10">
          
          {/* WITHOUT RALLY */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.5 }}
            className="space-y-6"
          >
            <div className="font-mono text-xs text-red-400/80 uppercase tracking-widest flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400/80" />
              WITHOUT RALLY
            </div>

            <ul className="space-y-4 font-sans text-sm sm:text-base text-white/50">
              <li className="flex items-center gap-3 border-b border-white/5 pb-3">
                <span className="font-mono text-xs text-white/30">01</span>
                <span>Scattered locations across messaging apps</span>
              </li>
              <li className="flex items-center gap-3 border-b border-white/5 pb-3">
                <span className="font-mono text-xs text-white/30">02</span>
                <span>Unanswered text messages while riding or driving</span>
              </li>
              <li className="flex items-center gap-3 border-b border-white/5 pb-3">
                <span className="font-mono text-xs text-white/30">03</span>
                <span>Uncertain progress and missing ETA clarity</span>
              </li>
              <li className="flex items-center gap-3 border-b border-white/5 pb-3">
                <span className="font-mono text-xs text-white/30">04</span>
                <span>Manual pull-over check-ins and delayed alerts</span>
              </li>
            </ul>
          </motion.div>

          {/* WITH RALLY */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="space-y-6"
          >
            <div className="font-mono text-xs text-emerald-400 uppercase tracking-widest flex items-center gap-2 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              WITH RALLY
            </div>

            <ul className="space-y-4 font-sans text-sm sm:text-base text-white font-medium">
              <li className="flex items-center gap-3 border-b border-white/10 pb-3">
                <span className="font-mono text-xs text-emerald-400 font-bold">01</span>
                <span>One unified live map for every member</span>
              </li>
              <li className="flex items-center gap-3 border-b border-white/10 pb-3">
                <span className="font-mono text-xs text-emerald-400 font-bold">02</span>
                <span>Real-time group status & telemetry streaming</span>
              </li>
              <li className="flex items-center gap-3 border-b border-white/10 pb-3">
                <span className="font-mono text-xs text-emerald-400 font-bold">03</span>
                <span>Automatic separation & route deviation alerts</span>
              </li>
              <li className="flex items-center gap-3 border-b border-white/10 pb-3">
                <span className="font-mono text-xs text-emerald-400 font-bold">04</span>
                <span>Complete trip history & automated post-trip recap</span>
              </li>
            </ul>
          </motion.div>

        </div>

      </div>
    </section>
  );
}
