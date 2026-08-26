'use client';

import React from 'react';
import { motion } from 'framer-motion';

const STATS = [
  { value: '6', label: 'members connected' },
  { value: '1', label: 'shared live map' },
  { value: '24/7', label: 'trip history' },
  { value: '1 tap', label: 'to alert the group' },
];

export default function ProductProof() {
  return (
    <section className="py-24 md:py-32 px-6 md:px-12 bg-background border-t border-white/10">
      <div className="max-w-5xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
          {STATS.map((stat, idx) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.4, delay: idx * 0.08 }}
              className="space-y-2 text-left"
            >
              <div className="text-4xl sm:text-6xl font-medium tracking-tight text-white font-mono">
                {stat.value}
              </div>
              <div className="text-xs sm:text-sm font-mono text-white/50 uppercase tracking-wider">
                {stat.label}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
