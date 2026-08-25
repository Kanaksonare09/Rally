'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';

const MotionLink = motion.create(Link);

export default function FinalCTA() {
  return (
    <section className="py-24 md:py-32 px-8 md:px-28 bg-background border-t border-border">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="text-3xl md:text-5xl tracking-[-1px] font-medium leading-tight mb-4">
          Start your next <span className="font-serif italic font-normal">journey together.</span>
        </h2>
        <p className="text-base text-muted-foreground mb-10">
          Create a Rally in seconds, or join one with a code from your group leader.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <MotionLink
            href="/register"
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
            className="inline-block bg-foreground text-background rounded-full px-8 py-3.5 text-base font-medium"
          >
            Get Started for Free
          </MotionLink>
          <Link
            href="/join-group"
            className="inline-block border border-border text-foreground rounded-full px-8 py-3.5 text-base font-medium hover:bg-white/5 transition-colors"
          >
            Join a Rally
          </Link>
        </div>
      </div>
    </section>
  );
}
