'use client';

import { motion } from 'framer-motion';
import StepItem from './StepItem';

const VIDEO_URL = '/assets/night-lake.mp4';

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.15, delayChildren: 0.2 },
  },
};

const item = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

interface Step {
  number: number;
  text: string;
}

export default function AuthHero({
  heading,
  subtitle,
  steps,
  activeStep,
}: {
  heading: string;
  subtitle: string;
  steps: Step[];
  activeStep: number;
}) {
  return (
    <div className="relative hidden lg:flex flex-col items-center justify-end pb-32 px-12 rounded-3xl overflow-hidden shadow-2xl h-full w-[52%]">
      <video
        className="absolute inset-0 w-full h-full object-cover"
        style={{ filter: 'saturate(1.15) contrast(1.05)' }}
        autoPlay
        muted
        loop
        playsInline
      >
        <source src={VIDEO_URL} type="video/mp4" />
      </video>

      {/* Bottom-only legibility fade for the content anchored below. */}
      <div
        className="absolute inset-x-0 bottom-0 h-[55%] pointer-events-none"
        style={{ background: 'linear-gradient(to bottom, transparent, hsl(var(--background)/0.75) 75%, hsl(var(--background)) 100%)' }}
      />

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="relative z-10 w-full max-w-xs space-y-8"
      >
        <motion.div variants={item}>
          <img src="/assets/rally-wordmark.png" alt="RALLY" className="h-10 w-auto mt-2" />
        </motion.div>

        <motion.div variants={item} className="space-y-2">
          <h1 className="text-4xl font-medium tracking-tight whitespace-nowrap text-foreground">{heading}</h1>
          <p className="text-white/60 text-sm leading-relaxed">{subtitle}</p>
        </motion.div>

        <motion.div variants={item} className="space-y-2">
          {steps.map((step) => (
            <StepItem key={step.number} number={step.number} text={step.text} active={step.number === activeStep} />
          ))}
        </motion.div>
      </motion.div>
    </div>
  );
}
