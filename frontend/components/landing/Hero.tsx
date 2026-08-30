'use client';

import { useRef } from 'react';
import Link from 'next/link';
import { motion, useScroll, useTransform } from 'framer-motion';
import Navbar from './Navbar';
import InteractiveDashboard from './InteractiveDashboard';

const MotionLink = motion.create(Link);

const VIDEO_URL = '/assets/night-lake.mp4';

export default function Hero() {
  const sectionRef = useRef<HTMLElement>(null);

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ['start start', 'end start'],
  });

  const heroY = useTransform(scrollYProgress, [0, 0.5], [0, -200]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const dashboardY = useTransform(scrollYProgress, [0, 1], [0, -250]);

  return (
    <section ref={sectionRef} className="relative min-h-screen overflow-hidden bg-background">
      <Navbar />

      <motion.div
        style={{ y: heroY, opacity: heroOpacity }}
        className="relative z-10 flex flex-col items-center text-center mt-16 md:mt-20 px-4"
      >
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0 }}
          className="liquid-glass inline-flex items-center gap-2 px-3 py-2 rounded-lg mb-6"
        >
          <span className="bg-foreground text-background rounded-md text-sm font-medium px-2 py-0.5">
            New
          </span>
          <span className="text-sm font-medium text-muted-foreground">
            Say Hello to RALLY v1.0
          </span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-5xl md:text-7xl tracking-[-2px] font-medium leading-tight md:leading-[1.15] mb-3 max-w-4xl"
        >
          Your Group&apos;s Movement. <br />
          <span className="font-serif italic font-normal">One Clear Overview.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          style={{ color: 'hsl(var(--hero-subtitle))' }}
          className="text-lg font-normal leading-6 opacity-90 mb-8 max-w-xl"
        >
          RALLY helps groups track location, safety, <br />
          and progress with precision.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
        >
          <MotionLink
            href="/register"
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
            className="inline-block bg-foreground text-background rounded-full px-8 py-3.5 text-base font-medium"
          >
            Get Started for Free
          </MotionLink>
        </motion.div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.4 }}
        className="relative w-screen mt-14"
        style={{ marginLeft: 'calc(-50vw + 50%)', aspectRatio: '16 / 9' }}
      >
        <video
          className="absolute inset-0 w-full h-full object-cover"
          style={{ filter: 'saturate(1.15) contrast(1.05)' }}
          src={VIDEO_URL}
          autoPlay
          muted
          loop
          playsInline
        />

        {/* Top fade — smooths the cut from the pure-black hero text above
            into the video instead of a hard edge. */}
        <div
          className="absolute top-0 left-0 right-0 h-32 z-30 pointer-events-none"
          style={{ background: 'linear-gradient(to top, transparent, hsl(var(--background)))' }}
        />

        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <motion.div
            style={{ y: dashboardY }}
            className="w-[90%] max-w-5xl"
          >
            <InteractiveDashboard />
          </motion.div>
        </div>

        <div
          className="absolute bottom-0 left-0 right-0 h-40 z-30 pointer-events-none"
          style={{ background: 'linear-gradient(to bottom, transparent, hsl(var(--background)))' }}
        />
      </motion.div>
    </section>
  );
}
