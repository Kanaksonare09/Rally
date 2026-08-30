'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Plus, Minus, HelpCircle, ArrowRight, X } from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

interface FAQData {
  id: string;
  category: 'GETTING STARTED' | 'TRIPS' | 'LIVE TRACKING' | 'SAFETY' | 'ACCOUNT & HISTORY';
  q: string;
  a: string;
  isFeatured?: boolean;
  note?: string;
}

const FAQ_ITEMS: FAQData[] = [
  {
    id: 'how-rally-works',
    category: 'GETTING STARTED',
    q: 'How does RALLY work?',
    a: 'RALLY brings your group onto a single, live map during trips. You create a group, invite members with a 6-character code, and start a trip. Live tracking, route divergence detection, and automatic safety alerts run in real time.',
    isFeatured: true,
  },
  {
    id: 'group-size',
    category: 'GETTING STARTED',
    q: 'How many people can be in one group?',
    a: "There's no hard cap on group size — RALLY is built for anything from a couple of friends on a weekend drive to a large expedition group.",
  },
  {
    id: 'leaving-group',
    category: 'GETTING STARTED',
    q: 'Can I leave a group after joining?',
    a: "Yes, at any time. If you're the group's leader, you'll need to hand off leadership to another active member first.",
  },
  {
    id: 'multiple-trips',
    category: 'TRIPS',
    q: 'Can more than one trip run at the same time?',
    a: "A group can only have one active trip at a time. You can still create a new trip in advance — it just won't start until the current one ends or is cancelled.",
  },
  {
    id: 'trip-history',
    category: 'ACCOUNT & HISTORY',
    q: 'Is my trip history saved after the trip ends?',
    a: "Yes — completed and cancelled trips stay in your group's history so they can be reviewed or replayed later. A group can't be deleted while its trip history still exists.",
  },
  {
    id: 'location-visibility',
    category: 'SAFETY',
    q: 'Who can see my location?',
    a: "Only other active members of the same group, and only for trips you're part of. Nobody outside your group can see your location or trip history.",
    note: 'Only active members of the relevant group can access location data.',
  },
  {
    id: 'signal-loss',
    category: 'LIVE TRACKING',
    q: 'What happens if I lose signal mid-trip?',
    a: 'Your last known position stays visible to the group, and a connectivity alert lets them know you’ve gone offline. Points sent after reconnecting are placed correctly in the timeline, even if they arrive out of order.',
  },
  {
    id: 'sos-button',
    category: 'SAFETY',
    q: 'What does the SOS button actually do?',
    a: 'It immediately shares your exact location with every active member of your group, so the people closest to you can respond fastest.',
  },
];

const CATEGORIES = [
  'ALL',
  'GETTING STARTED',
  'TRIPS',
  'LIVE TRACKING',
  'SAFETY',
  'ACCOUNT & HISTORY',
];

const SECTION_HEADERS = [
  { id: 'sec-getting-started', num: '01', title: 'GETTING STARTED', category: 'GETTING STARTED' },
  { id: 'sec-trips', num: '02', title: 'TRIPS', category: 'TRIPS' },
  { id: 'sec-live-tracking', num: '03', title: 'LIVE TRACKING', category: 'LIVE TRACKING' },
  { id: 'sec-safety', num: '04', title: 'SAFETY', category: 'SAFETY' },
  { id: 'sec-account-history', num: '05', title: 'ACCOUNT & HISTORY', category: 'ACCOUNT & HISTORY' },
];

export default function FAQInteractive() {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [openId, setOpenId] = useState<string | null>('how-rally-works');
  const [scrollProgress, setScrollProgress] = useState<number>(0);
  const [activeSecId, setActiveSecId] = useState<string>('sec-getting-started');

  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Keyboard shortcut listener ('/' key focuses search input)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== searchInputRef.current) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Track reading progress and active section on scroll
  useEffect(() => {
    const handleScroll = () => {
      const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (totalHeight > 0) {
        setScrollProgress(Math.min(1, Math.max(0, window.scrollY / totalHeight)));
      }

      const scrollPos = window.scrollY + 200;
      for (let i = SECTION_HEADERS.length - 1; i >= 0; i--) {
        const el = document.getElementById(SECTION_HEADERS[i].id);
        if (el && el.offsetTop <= scrollPos) {
          setActiveSecId(SECTION_HEADERS[i].id);
          break;
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Hash deep linking support (e.g. /faq#sos-button)
  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const targetId = window.location.hash.substring(1);
      const matchedItem = FAQ_ITEMS.find((item) => item.id === targetId);
      if (matchedItem) {
        setOpenId(matchedItem.id);
        setTimeout(() => {
          const el = document.getElementById(`faq-item-${targetId}`);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
      }
    }
  }, []);

  // Filter FAQ items by category and search query
  const filteredFAQs = useMemo(() => {
    return FAQ_ITEMS.filter((item) => {
      const matchesCategory =
        selectedCategory === 'ALL' || item.category === selectedCategory;
      const qLower = item.q.toLowerCase();
      const aLower = item.a.toLowerCase();
      const catLower = item.category.toLowerCase();
      const queryLower = searchQuery.toLowerCase().trim();

      const matchesSearch =
        !queryLower ||
        qLower.includes(queryLower) ||
        aLower.includes(queryLower) ||
        catLower.includes(queryLower);

      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchQuery]);

  const toggleQuestion = (id: string) => {
    setOpenId((prev) => (prev === id ? null : id));
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      const top = el.getBoundingClientRect().top + window.scrollY - 120;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  };

  return (
    <div className="bg-[#000000] text-white min-h-screen font-sans selection:bg-white/20 selection:text-white">
      {/* 23. Reading Progress Bar (1px thin line at top) */}
      <div
        className="fixed top-0 left-0 h-[2px] bg-white z-50 transition-all duration-75"
        style={{ width: `${scrollProgress * 100}%` }}
      />

      {/* Global Navbar */}
      <Navbar />

      {/* 2. COMPACT HERO SECTION (~35-40vh) */}
      <section className="pt-20 pb-8 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono tracking-[0.2em] text-white/70 uppercase mb-6"
        >
          <HelpCircle className="w-3.5 h-3.5 text-white/70" />
          FAQ
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl font-medium tracking-tight text-white max-w-3xl leading-[1.1]"
        >
          Common <br />
          <span className="font-serif italic font-normal text-white/90 tracking-normal">
            questions.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-4 text-base sm:text-lg text-white/60 max-w-xl font-normal leading-relaxed"
        >
          Everything people usually ask before starting their first Rally.
        </motion.p>
      </section>

      {/* 3 & 4. SEARCH INTERFACE & CATEGORY NAVIGATION */}
      <section className="px-6 max-w-3xl mx-auto my-6 flex flex-col items-center">
        {/* Search Field (600-700px width) */}
        <div className="relative w-full max-w-[680px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40 pointer-events-none" />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search questions..."
            className="w-full bg-[#030303] text-white placeholder-white/40 pl-11 pr-14 py-3.5 rounded-xl border border-white/20 text-sm font-sans focus:outline-none focus:border-white transition-all shadow-inner"
          />
          {searchQuery ? (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-4 top-1/2 -translate-y-1/2 p-1 text-white/40 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          ) : (
            <span className="absolute right-4 top-1/2 -translate-y-1/2 px-2 py-0.5 rounded bg-white/10 text-white/50 text-[10px] font-mono border border-white/10 pointer-events-none">
              /
            </span>
          )}
        </div>

        {/* Categories Bar (Horizontally scrollable on mobile) */}
        <div className="w-full max-w-[680px] mt-6 flex items-center gap-2 overflow-x-auto pb-2 no-scrollbar font-mono text-xs text-white/50 border-b border-white/10">
          {CATEGORIES.map((cat) => {
            const isActive = selectedCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-md whitespace-nowrap transition-all duration-200 ${
                  isActive
                    ? 'text-white bg-white/10 font-bold border-b-2 border-white'
                    : 'hover:text-white hover:bg-white/5'
                }`}
              >
                {cat}
              </button>
            );
          })}
        </div>
      </section>

      {/* 5, 6, 7, 13. MAIN FAQ LAYOUT & SIDE NAV (25% / 75% Desktop) */}
      <div className="max-w-[1240px] mx-auto px-6 py-12 flex flex-col md:flex-row gap-12 lg:gap-16">
        
        {/* 13. LEFT STICKY SIDE NAVIGATION (25% Desktop) */}
        <aside className="hidden md:block w-1/4 shrink-0">
          <div className="sticky top-28 font-mono text-xs space-y-6">
            <div className="text-[10px] text-white/40 uppercase tracking-[0.2em] flex items-center justify-between">
              <span>FAQ SECTIONS</span>
              <span className="text-white/60 font-bold">{filteredFAQs.length} Qs</span>
            </div>

            <nav className="space-y-3" aria-label="FAQ Sections">
              {SECTION_HEADERS.map((sec) => {
                const isActive = activeSecId === sec.id;
                return (
                  <button
                    key={sec.id}
                    onClick={() => scrollToSection(sec.id)}
                    className={`w-full text-left flex items-center gap-3 py-1 transition-all duration-200 ${
                      isActive ? 'text-white font-semibold' : 'text-white/40 hover:text-white/80'
                    }`}
                  >
                    <span 
                      className={`w-[2px] h-4 rounded-full transition-all ${
                        isActive ? 'bg-white scale-y-100' : 'bg-transparent scale-y-0'
                      }`} 
                    />
                    <span className="text-[10px] opacity-50">{sec.num}</span>
                    <span className="truncate">{sec.title}</span>
                  </button>
                );
              })}
            </nav>
          </div>
        </aside>

        {/* 7. RIGHT MAIN FAQ CONTENT (75% Desktop, 760-820px width) */}
        <main className="w-full md:w-3/4 max-w-[820px] space-y-16">
          
          {/* FAQ Counter Readout */}
          <div className="flex items-center justify-between font-mono text-xs text-white/40 pb-4 border-b border-white/10">
            <span>{filteredFAQs.length} QUESTIONS AVAILABLE</span>
            <span>UPDATED RECENTLY</span>
          </div>

          {filteredFAQs.length === 0 ? (
            /* No Results Search State */
            <div className="py-16 text-center space-y-3 font-mono text-xs">
              <div className="text-white text-base font-sans font-medium">No questions found.</div>
              <div className="text-white/50">Try another search or select &quot;ALL&quot; categories.</div>
            </div>
          ) : (
            /* Grouped Questions List */
            SECTION_HEADERS.map((secHeader) => {
              const secQuestions = filteredFAQs.filter(
                (item) => item.category === secHeader.category
              );

              if (secQuestions.length === 0) return null;

              return (
                <section key={secHeader.id} id={secHeader.id} className="scroll-mt-28 space-y-6">
                  {/* Subtle Section Header */}
                  <div className="flex items-center gap-3 font-mono text-xs text-white/40 tracking-[0.2em] border-b border-white/10 pb-3">
                    <span>{secHeader.num}</span>
                    <span className="text-white font-bold">{secHeader.title}</span>
                  </div>

                  {/* Accordion List */}
                  <div className="divide-y divide-white/10">
                    {secQuestions.map((item) => {
                      const isOpen = openId === item.id;
                      return (
                        <div
                          key={item.id}
                          id={`faq-item-${item.id}`}
                          className={`transition-all duration-200 ${
                            item.isFeatured ? 'py-6 px-4 rounded-xl bg-white/[0.03] border border-white/15 my-4' : 'py-5'
                          }`}
                        >
                          <button
                            onClick={() => toggleQuestion(item.id)}
                            aria-expanded={isOpen}
                            aria-controls={`faq-answer-${item.id}`}
                            className="w-full flex items-center justify-between gap-6 text-left group focus:outline-none"
                          >
                            <span
                              className={`text-base sm:text-lg font-medium transition-colors ${
                                isOpen ? 'text-white font-semibold' : 'text-white/80 group-hover:text-white'
                              }`}
                            >
                              {item.q}
                            </span>
                            <span className="w-6 h-6 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-white/60 group-hover:text-white transition-all shrink-0">
                              {isOpen ? <Minus className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                            </span>
                          </button>

                          <AnimatePresence initial={false}>
                            {isOpen && (
                              <motion.div
                                id={`faq-answer-${item.id}`}
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                                className="overflow-hidden"
                              >
                                <div className="pt-4 text-sm sm:text-base text-white/65 leading-relaxed space-y-4 max-w-2xl font-normal">
                                  <p>{item.a}</p>

                                  {/* Editorial Callout Note inside answer if applicable */}
                                  {item.note && (
                                    <div className="mt-3 p-3.5 rounded bg-white/[0.03] border-l-2 border-white/40 text-xs font-mono space-y-1">
                                      <div className="text-white font-bold uppercase tracking-wider">NOTE</div>
                                      <div className="text-white/60 font-sans text-sm">{item.note}</div>
                                    </div>
                                  )}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      );
                    })}
                  </div>
                </section>
              );
            })
          )}

        </main>

      </div>

      {/* 24. FINAL STILL HAVE A QUESTION SECTION */}
      <section className="pb-28 px-6 max-w-3xl mx-auto text-center">
        <div className="pt-16 border-t border-white/10 flex flex-col items-center">
          <h3 className="text-3xl sm:text-4xl font-medium text-white tracking-tight">
            Still have a question?
          </h3>

          <p className="mt-3 text-base text-white/60 font-normal font-sans">
            We&apos;re here to help.
          </p>

          <div className="mt-8">
            <Link
              href="/contact"
              className="px-8 py-3.5 rounded-full bg-white text-black text-xs font-mono font-semibold tracking-wider uppercase hover:bg-white/90 transition-all duration-200 shadow-[0_0_30px_rgba(255,255,255,0.2)] hover:scale-[1.02] inline-block"
            >
              Contact us
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <Footer />
    </div>
  );
}
