'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

export default function InteractiveDashboard() {
  const [distance, setDistance] = useState(4.8);
  const [health, setHealth] = useState(94);
  const [syncStatus, setSyncStatus] = useState(true);

  // Simulate live data changes
  useEffect(() => {
    const interval = setInterval(() => {
      setDistance((prev) => +(prev + 0.1).toFixed(1));
      setHealth((prev) => (Math.random() > 0.5 ? Math.min(100, prev + 1) : Math.max(90, prev - 1)));
      setSyncStatus((prev) => !prev);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-full max-w-5xl aspect-[16/10] rounded-2xl bg-[#09090b]/95 backdrop-blur-xl border border-white/10 shadow-2xl shadow-black/80 flex flex-col overflow-hidden font-sans">
      {/* Window Header */}
      <div className="h-12 border-b border-white/5 flex items-center justify-between px-6 shrink-0 relative">
        <div className="flex gap-2 relative z-10">
          <div className="w-3 h-3 rounded-full bg-white/10"></div>
          <div className="w-3 h-3 rounded-full bg-white/10"></div>
          <div className="w-3 h-3 rounded-full bg-white/10"></div>
        </div>
        
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <span className="text-[10px] tracking-widest text-white/30 font-medium uppercase">
            Rally / Live Group
          </span>
        </div>

        <div className="flex items-center gap-2 bg-white/5 px-2.5 py-1 rounded-full relative z-10">
          <motion.div 
            animate={{ opacity: [1, 0.4, 1] }} 
            transition={{ duration: 2, repeat: Infinity }}
            className="w-1.5 h-1.5 rounded-full bg-emerald-500"
          />
          <span className="text-[10px] font-medium text-white/50 tracking-wider">LIVE</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <div className="w-48 border-r border-white/5 p-4 flex flex-col gap-1 shrink-0">
          {[
            { name: 'Overview', active: true },
            { name: 'Live Group', active: false },
            { name: 'Trips', active: false },
            { name: 'Alerts', active: false },
            { name: 'Members', active: false },
          ].map((item) => (
            <div 
              key={item.name}
              className={`px-3 py-2 rounded-md text-[13px] font-medium transition-colors cursor-pointer ${
                item.active 
                  ? 'bg-white/10 text-white' 
                  : 'text-white/40 hover:text-white hover:bg-white/5'
              }`}
            >
              {item.name}
            </div>
          ))}
        </div>

        {/* Dashboard Area */}
        <div className="flex-1 p-6 flex flex-col gap-6 overflow-hidden">
          {/* Top Cards */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-[#121214] border border-white/5 rounded-xl p-4 flex flex-col gap-1 shadow-inner">
              <span className="text-[10px] text-white/40 tracking-wider uppercase">Group Health</span>
              <motion.span 
                key={health}
                initial={{ opacity: 0.5, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-2xl font-semibold text-white"
              >
                {health}%
              </motion.span>
            </div>
            <div className="bg-[#121214] border border-white/5 rounded-xl p-4 flex flex-col gap-1 shadow-inner">
              <span className="text-[10px] text-white/40 tracking-wider uppercase">Members</span>
              <span className="text-2xl font-semibold text-white">6 / 6</span>
            </div>
            <div className="bg-[#121214] border border-white/5 rounded-xl p-4 flex flex-col gap-1 shadow-inner">
              <span className="text-[10px] text-white/40 tracking-wider uppercase">Distance</span>
              <motion.span 
                key={distance}
                initial={{ opacity: 0.5, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-2xl font-semibold text-white"
              >
                {distance}km
              </motion.span>
            </div>
            <div className="bg-[#121214] border border-white/5 rounded-xl p-4 flex flex-col gap-1 shadow-inner">
              <span className="text-[10px] text-white/40 tracking-wider uppercase">Risk</span>
              <span className="text-2xl font-semibold text-white">Low</span>
            </div>
          </div>

          {/* Map/Chart Area */}
          <div className="flex-1 bg-[#121214] border border-white/5 rounded-xl relative overflow-hidden flex shadow-inner">
            {/* Grid Background */}
            <div 
              className="absolute inset-0 opacity-20"
              style={{
                backgroundImage: `linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)`,
                backgroundSize: '40px 40px',
                maskImage: 'radial-gradient(ellipse at center, black 40%, transparent 80%)',
                WebkitMaskImage: 'radial-gradient(ellipse at center, black 40%, transparent 80%)'
              }}
            />

            {/* Path Line */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" preserveAspectRatio="none">
              <motion.path 
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 0.3 }}
                transition={{ duration: 2, ease: "easeOut" }}
                d="M 50 250 L 350 150 L 600 50" 
                fill="none" 
                stroke="white" 
                strokeWidth="2" 
                className="drop-shadow-lg"
              />
            </svg>

            {/* Nodes */}
            <motion.div 
              animate={{ 
                x: [0, 5, 0, -5, 0],
                y: [0, -3, 0, 3, 0]
              }}
              transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
              className="absolute left-[50px] top-[250px] flex items-center justify-center -translate-x-1/2 -translate-y-1/2"
            >
              <div className="relative">
                <div className="w-10 h-10 rounded-full bg-white/5 absolute -inset-3.5 animate-ping opacity-20"></div>
                <div className="w-3 h-3 rounded-full bg-white shadow-[0_0_10px_white]"></div>
                <div className="absolute top-5 left-1/2 -translate-x-1/2 bg-black/80 border border-white/10 text-white text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap">
                  Ben
                </div>
              </div>
            </motion.div>

            <motion.div 
              animate={{ 
                x: [0, -8, 0, 8, 0],
                y: [0, 5, 0, -5, 0]
              }}
              transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
              className="absolute left-[350px] top-[150px] flex items-center justify-center -translate-x-1/2 -translate-y-1/2"
            >
              <div className="relative">
                <div className="w-3 h-3 rounded-full bg-white shadow-[0_0_10px_white]"></div>
                <div className="absolute left-6 top-1/2 -translate-y-1/2 bg-black/80 border border-white/10 text-white text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap">
                  Alex
                </div>
              </div>
            </motion.div>

            <motion.div 
              animate={{ 
                x: [0, 4, 0, -4, 0],
                y: [0, -4, 0, 4, 0]
              }}
              transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
              className="absolute left-[400px] top-[170px] flex items-center justify-center -translate-x-1/2 -translate-y-1/2"
            >
              <div className="relative">
                <div className="w-10 h-10 rounded-full bg-white/5 absolute -inset-3.5 animate-ping opacity-20 delay-500"></div>
                <div className="w-3 h-3 rounded-full bg-white shadow-[0_0_10px_white]"></div>
                <div className="absolute left-6 top-1/2 -translate-y-1/2 bg-black/80 border border-white/10 text-white text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap">
                  Maya
                </div>
              </div>
            </motion.div>

            <motion.div 
              animate={{ 
                x: [0, -5, 0, 5, 0],
                y: [0, -2, 0, 2, 0]
              }}
              transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
              className="absolute left-[600px] top-[50px] flex items-center justify-center -translate-x-1/2 -translate-y-1/2"
            >
              <div className="relative">
                <div className="w-12 h-12 rounded-full border border-white/20 absolute -inset-4 opacity-50"></div>
                <div className="w-3 h-3 rounded-full bg-white shadow-[0_0_10px_white]"></div>
              </div>
            </motion.div>

            {/* Bottom Status Pill */}
            <div className="absolute bottom-4 left-4 bg-black/60 backdrop-blur border border-white/10 rounded-lg px-3 py-2 flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full ${syncStatus ? 'bg-emerald-500' : 'bg-emerald-500/50'}`}></div>
              <span className="text-[10px] font-mono text-white/50 uppercase tracking-widest">
                Convoy Synced @ 5hz
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
