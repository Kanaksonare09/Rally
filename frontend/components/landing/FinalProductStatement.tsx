'use client';

import React from 'react';
import { motion } from 'framer-motion';

export default function FinalProductStatement() {
  return (
    <section className="py-32 md:py-44 px-6 md:px-12 bg-background border-t border-white/10 text-center flex flex-col items-center">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Staggered Typography Statement */}
        <motion.h2 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.7 }}
          className="text-4xl sm:text-6xl md:text-7xl tracking-tight font-medium leading-[1.12] text-white"
        >
          Know <span className="font-serif italic font-normal text-white/95">where</span> everyone is. <br />
          Know when something <span className="font-serif italic font-normal text-white/95">changes.</span> <br />
          Know what <span className="font-serif italic font-normal text-white/95">happened.</span>
        </motion.h2>

        {/* Animated Route Line Underneath */}
        <div className="w-full max-w-xs mx-auto pt-6 flex items-center justify-center">
          <svg className="w-full h-8 overflow-visible" viewBox="0 0 200 20">
            <path
              d="M 0 10 Q 100 0 200 10"
              fill="none"
              stroke="rgba(255,255,255,0.2)"
              strokeWidth="2"
            />
            <path
              d="M 0 10 Q 100 0 200 10"
              fill="none"
              stroke="#22d3ee"
              strokeWidth="2"
              strokeDasharray="4 4"
              className="animate-[dash_10s_linear_infinite]"
            />
            <circle cx="0" cy="10" r="3" fill="#38bdf8" />
            <circle cx="200" cy="10" r="3" fill="#34d399" />
          </svg>
        </div>

      </div>
    </section>
  );
}
