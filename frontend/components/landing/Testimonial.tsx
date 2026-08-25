'use client';

import { useRef } from 'react';
import { motion, useScroll, useTransform, MotionValue } from 'framer-motion';

const QUOTE =
  "RALLY changed how our team moves together. We spot risk earlier, close the gap faster, and every trip feels less like guesswork and more like a plan we can trust.";

const AUTHOR = {
  name: 'Brooklyn Simmons',
  role: 'Trip Lead, Alpine Collective',
};

function Word({
  word,
  index,
  total,
  scrollYProgress,
}: {
  word: string;
  index: number;
  total: number;
  scrollYProgress: MotionValue<number>;
}) {
  const start = index / total;
  const end = (index + 1) / total;
  const opacity = useTransform(scrollYProgress, [start, end], [0.2, 1]);
  const color = useTransform(scrollYProgress, [start, end], ['hsl(0 0% 35%)', 'hsl(0 0% 100%)']);

  return (
    <motion.span style={{ opacity, color }} className="mr-[0.3em]">
      {word}
    </motion.span>
  );
}

export default function Testimonial() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start end', 'end center'],
  });

  const words = QUOTE.split(' ');

  return (
    <section id="testimonial" className="min-h-screen flex items-center py-24 md:py-32 px-8 md:px-28 bg-background">
      <div ref={containerRef} className="max-w-3xl mx-auto flex flex-col items-start gap-10">
        <img src="/assets/quote-symbol.svg" alt="" className="w-14 h-10 object-contain" />

        <p className="text-4xl md:text-5xl font-medium leading-[1.2] flex flex-wrap">
          {words.map((word, i) => (
            <Word key={i} word={word} index={i} total={words.length} scrollYProgress={scrollYProgress} />
          ))}
          <span className="text-muted-foreground ml-2">&rdquo;</span>
        </p>

        <div className="flex items-center gap-4">
          <img
            src="/assets/testimonial-avatar.svg"
            alt={AUTHOR.name}
            className="w-14 h-14 rounded-full border-[3px] border-foreground object-cover"
          />
          <div>
            <p className="text-base font-semibold leading-7 text-foreground">{AUTHOR.name}</p>
            <p className="text-sm font-normal leading-5 text-muted-foreground">{AUTHOR.role}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
