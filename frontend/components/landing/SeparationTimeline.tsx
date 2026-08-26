'use client';

import React from 'react';
import { motion } from 'framer-motion';

const EVENTS = [
  {
    time: '09:42',
    title: 'Group leaves together.',
    detail: 'All 6 devices active on primary route • Baseline pace 48 km/h',
    status: 'normal',
  },
  {
    time: '09:51',
    title: 'Maya falls 180m behind.',
    detail: 'Pace mismatch detected on Sector 2 climb • Distance delta increasing',
    status: 'warning',
  },
  {
    time: '09:52',
    title: 'RALLY detects separation.',
    detail: 'Automated threshold trigger: Distance > 150m • Silence delay bypassed',
    status: 'alert',
  },
  {
    time: '09:53',
    title: 'The group is notified.',
    detail: 'Low-priority subtle chime sent to lead rider & map highlight enabled',
    status: 'info',
  },
  {
    time: '09:55',
    title: 'Maya rejoins the route.',
    detail: 'Gap closed to 25m • Group status restored to green',
    status: 'resolved',
  },
];

export default function SeparationTimeline() {
  return (
    <section className="py-28 md:py-36 px-6 md:px-12 bg-background border-t border-white/10">
      <div className="max-w-4xl mx-auto space-y-16">
        
        {/* Header */}
        <div className="max-w-2xl space-y-4">
          <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
            SYSTEM INTELLIGENCE LOG
          </div>

          <h2 className="text-3xl md:text-5xl tracking-tight font-medium leading-[1.15] text-white">
            RALLY notices the moment <br />
            <span className="font-serif italic font-normal text-white/90">
              something changes.
            </span>
          </h2>
        </div>

        {/* Operating Vertical Timeline */}
        <div className="relative pl-6 sm:pl-10 space-y-10 font-mono">
          
          {/* Vertical Connecting Line */}
          <div className="absolute top-3 bottom-3 left-[11px] sm:left-[19px] w-[1px] bg-white/15" />

          {EVENTS.map((event, idx) => {
            const isAlert = event.status === 'alert' || event.status === 'warning';
            return (
              <motion.div
                key={event.time}
                initial={{ opacity: 0, x: -15 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: '-60px' }}
                transition={{ duration: 0.4, delay: idx * 0.1 }}
                className="relative flex items-start gap-4 sm:gap-8 group"
              >
                {/* Timeline Dot Node */}
                <div className={`absolute -left-[23px] sm:-left-[31px] top-1.5 w-3.5 h-3.5 rounded-full border-2 bg-background transition-all ${
                  isAlert 
                    ? 'border-amber-400 bg-amber-400/20 shadow-[0_0_10px_rgba(251,191,36,0.8)]' 
                    : event.status === 'resolved'
                    ? 'border-emerald-400 bg-emerald-400/20'
                    : 'border-white/40 group-hover:border-white'
                }`} />

                {/* Event Time */}
                <div className="w-14 sm:w-16 shrink-0 text-xs font-bold text-white/50 tracking-wider">
                  {event.time}
                </div>

                {/* Event Details */}
                <div className="space-y-1">
                  <h3 className={`text-base sm:text-lg font-sans font-medium tracking-tight ${
                    isAlert ? 'text-amber-300' : 'text-white'
                  }`}>
                    {event.title}
                  </h3>
                  <p className="text-xs text-white/50 font-normal leading-relaxed">
                    {event.detail}
                  </p>
                </div>
              </motion.div>
            );
          })}

        </div>

      </div>
    </section>
  );
}
