'use client';

import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

export interface DetailItem {
  // A rendered element (`<Icon className="..." />`), not a component
  // reference — see MarketingHero.tsx for why.
  icon: any;
  title: string;
  description: string;
}

export default function DetailGrid({
  heading,
  subheading,
  items,
  columns = 2,
}: {
  heading?: string;
  subheading?: string;
  items: DetailItem[];
  columns?: 2 | 3;
}) {
  return (
    <section className="py-24 md:py-28 px-8 md:px-28 bg-background">
      <div className="max-w-5xl mx-auto">
        {heading && (
          <div className="max-w-xl mb-16">
            <h2 className="text-2xl md:text-3xl tracking-[-1px] font-medium leading-tight mb-3">{heading}</h2>
            {subheading && <p className="text-base text-muted-foreground leading-relaxed">{subheading}</p>}
          </div>
        )}

        <div
          className={`grid sm:grid-cols-2 ${columns === 3 ? 'lg:grid-cols-3' : ''} gap-px bg-border rounded-2xl overflow-hidden border border-border`}
        >
          {items.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className="bg-background p-8"
            >
              <div className="mb-5">{item.icon}</div>
              <h3 className="text-lg font-medium text-foreground mb-2">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
