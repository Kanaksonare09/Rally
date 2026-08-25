'use client';

import { motion } from 'framer-motion';

const item = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function StepItem({
  number,
  text,
  active = false,
}: {
  number: number;
  text: string;
  active?: boolean;
}) {
  return (
    <motion.div
      variants={item}
      className={`flex items-center gap-3 rounded-xl px-4 py-3 border transition-colors ${
        active ? 'bg-foreground text-background border-foreground' : 'bg-white/[0.04] text-foreground border-transparent'
      }`}
    >
      <span
        className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold shrink-0 ${
          active ? 'bg-background text-foreground' : 'bg-white/10 text-white/40'
        }`}
      >
        {number}
      </span>
      <span className="text-sm font-medium">{text}</span>
    </motion.div>
  );
}
