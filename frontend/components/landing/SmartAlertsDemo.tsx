'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bell, AlertTriangle, Navigation, WifiOff, CheckCircle2 } from 'lucide-react';

const ALERTS_DATA = [
  {
    id: 1,
    type: 'SEPARATION DETECTED',
    icon: AlertTriangle,
    color: 'text-amber-400',
    borderColor: 'border-amber-500/30',
    bgColor: 'bg-amber-500/10',
    message: 'Maya is 420m behind the group.',
    time: 'JUST NOW',
  },
  {
    id: 2,
    type: 'ROUTE DEVIATION',
    icon: Navigation,
    color: 'text-cyan-400',
    borderColor: 'border-cyan-500/30',
    bgColor: 'bg-cyan-500/10',
    message: 'Alex has moved 180m off the planned route.',
    time: '1m AGO',
  },
  {
    id: 3,
    type: 'CONNECTIVITY LOST',
    icon: WifiOff,
    color: 'text-red-400',
    borderColor: 'border-red-500/30',
    bgColor: 'bg-red-500/10',
    message: "Ben's device has stopped reporting.",
    time: '2m AGO',
  },
  {
    id: 4,
    type: 'GROUP REJOINED',
    icon: CheckCircle2,
    color: 'text-emerald-400',
    borderColor: 'border-emerald-500/30',
    bgColor: 'bg-emerald-500/10',
    message: 'Maya is back with the group.',
    time: '3m AGO',
  },
];

export default function SmartAlertsDemo() {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % ALERTS_DATA.length);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  const currentAlert = ALERTS_DATA[activeIndex];

  return (
    <section className="py-28 md:py-36 px-6 md:px-12 bg-background border-t border-white/10">
      <div className="max-w-4xl mx-auto space-y-16 text-center flex flex-col items-center">
        
        {/* Header */}
        <div className="max-w-2xl space-y-4">
          <div className="font-mono text-xs text-white/40 uppercase tracking-[0.2em]">
            INTELLIGENT FILTERING
          </div>

          <h2 className="text-3xl md:text-5xl md:text-6xl tracking-tight font-medium leading-[1.08] text-white">
            Not every movement needs attention. <br />
            <span className="font-serif italic font-normal text-white/95">
              Only the ones that matter.
            </span>
          </h2>
        </div>

        {/* Dynamic Alert Notification Simulation Area */}
        <div className="w-full max-w-lg min-h-[160px] flex items-center justify-center relative">
          
          <AnimatePresence mode="wait">
            <motion.div
              key={currentAlert.id}
              initial={{ opacity: 0, y: 15, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -15, scale: 0.96 }}
              transition={{ duration: 0.45, ease: 'easeOut' }}
              className={`w-full p-6 rounded-2xl bg-[#08090C] border ${currentAlert.borderColor} backdrop-blur-xl shadow-[0_20px_60px_rgba(0,0,0,0.8)] flex items-start gap-4 text-left font-mono`}
            >
              <div className={`p-3 rounded-xl ${currentAlert.bgColor} ${currentAlert.color} shrink-0`}>
                <currentAlert.icon className="w-6 h-6" />
              </div>

              <div className="space-y-1 flex-1">
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-bold tracking-wider uppercase ${currentAlert.color}`}>
                    {currentAlert.type}
                  </span>
                  <span className="text-[10px] text-white/40">
                    {currentAlert.time}
                  </span>
                </div>
                <p className="text-sm font-sans font-medium text-white pt-1">
                  {currentAlert.message}
                </p>
              </div>
            </motion.div>
          </AnimatePresence>

        </div>

        {/* Pagination Dots Indicator */}
        <div className="flex items-center justify-center gap-2">
          {ALERTS_DATA.map((_, i) => (
            <button
              key={i}
              onClick={() => setActiveIndex(i)}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                activeIndex === i ? 'w-8 bg-white' : 'w-1.5 bg-white/20'
              }`}
            />
          ))}
        </div>

      </div>
    </section>
  );
}
