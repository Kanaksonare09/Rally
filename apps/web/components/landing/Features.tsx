'use client';

import { motion } from 'framer-motion';
import { Map, BellRing, Route, Siren } from 'lucide-react';

const FEATURES = [
  {
    icon: Map,
    title: 'Live group map',
    description: 'See every member, your route, and the destination on one live map — updated in real time.',
  },
  {
    icon: BellRing,
    title: 'Smart alerts',
    description: 'Separation, route deviations, connectivity loss, and unexpected stops surface the moment they happen.',
  },
  {
    icon: Route,
    title: 'Trip intelligence',
    description: 'Every journey ends with a safety score, a route replay, and a clear summary of what happened.',
  },
  {
    icon: Siren,
    title: 'One-tap SOS',
    description: 'A single confirmation shares your exact location with the whole group when it matters most.',
  },
];

export default function Features() {
  return (
    <section id="features" className="py-24 md:py-32 px-8 md:px-28 bg-background">
      <div className="max-w-5xl mx-auto">
        <div className="max-w-xl mb-16">
          <h2 className="text-3xl md:text-4xl tracking-[-1px] font-medium leading-tight mb-3">
            Everything a group <span className="font-serif italic font-normal">needs to move together.</span>
          </h2>
          <p className="text-base text-muted-foreground leading-relaxed">
            RALLY combines live location, alerts, and trip history into one clear command center.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-px bg-border rounded-2xl overflow-hidden border border-border">
          {FEATURES.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="bg-background p-8"
            >
              <feature.icon className="w-5 h-5 text-foreground mb-5" strokeWidth={1.5} />
              <h3 className="text-lg font-medium text-foreground mb-2">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
