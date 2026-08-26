'use client';

import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

export default function MarketingHero({
  icon,
  eyebrow,
  title,
  titleAccent,
  description,
}: {
  // A rendered element, not a component reference — component references
  // (functions) can't cross the server -> client component boundary,
  // since this is a 'use client' component receiving props from a server
  // component page. Pass `<Icon className="..." />`, not `Icon`.
  icon: any;
  eyebrow: string;
  title: string;
  titleAccent?: string;
  description: string;
}) {
  return (
    <section className="pt-44 pb-20 md:pt-52 md:pb-28 px-8 md:px-28 bg-background border-b border-border">
      <div className="max-w-3xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-white/[0.03] text-xs font-medium text-muted-foreground mb-6"
        >
          {icon}
          {eyebrow}
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05 }}
          className="text-4xl md:text-6xl tracking-[-1.5px] font-medium leading-[1.1]"
        >
          {title}{' '}
          {titleAccent && <span className="font-serif italic font-normal">{titleAccent}</span>}
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-base md:text-lg text-muted-foreground leading-relaxed mt-6 max-w-xl mx-auto"
        >
          {description}
        </motion.p>
      </div>
    </section>
  );
}
