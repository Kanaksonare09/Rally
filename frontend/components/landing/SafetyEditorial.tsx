'use client';

import React from 'react';
import { motion } from 'framer-motion';

const PRINCIPLES = [
  {
    title: 'PRIVATE BY DEFAULT',
    desc: 'Location is visible only to the active group members during an active trip.',
  },
  {
    title: 'ONE-TAP SOS',
    desc: 'Share your exact coordinates with everyone in the group when it matters most.',
  },
  {
    title: 'LEAVE WHEN YOU WANT',
    desc: 'Every member stays in full control of their participation and location sharing.',
  },
];

export default function SafetyEditorial() {
  return (
    <section className="py-28 md:py-36 px-6 md:px-12 bg-background border-t border-white/10">
      <div className="max-w-5xl mx-auto space-y-16">
        
        {/* Header */}
        <div className="max-w-3xl space-y-4">
          <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
            SAFETY & PRIVACY DESIGN
          </div>

          <h2 className="text-3xl md:text-5xl md:text-6xl tracking-tight font-medium leading-[1.08] text-white">
            Safety should be present <br />
            <span className="font-serif italic font-normal text-white/95">
              without being distracting.
            </span>
          </h2>

          <p className="text-base sm:text-lg text-white/60 font-normal leading-relaxed max-w-xl pt-2">
            RALLY stays quiet when everything is fine and becomes visible when something isn't.
          </p>
        </div>

        {/* 3 Large Horizontal Typographic Statements */}
        <div className="border-t border-white/10 divide-y divide-white/10">
          {PRINCIPLES.map((principle, i) => (
            <motion.div
              key={principle.title}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="py-10 flex flex-col md:flex-row md:items-center justify-between gap-4 md:gap-12"
            >
              <h3 className="text-xl sm:text-3xl font-mono font-bold tracking-tight text-white uppercase md:w-1/2">
                {principle.title}
              </h3>
              <p className="text-sm sm:text-base text-white/60 font-normal leading-relaxed md:w-1/2">
                {principle.desc}
              </p>
            </motion.div>
          ))}
        </div>

      </div>
    </section>
  );
}
