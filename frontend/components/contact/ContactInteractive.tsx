'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, ArrowRight, Github, Mail, CheckCircle2, AlertCircle } from 'lucide-react';
import Navbar from '@/components/landing/Navbar';
import Footer from '@/components/landing/Footer';

const CONTACT_EMAIL = 'hello@joinrally.app';

export default function ContactInteractive() {
  const [name, setName] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [message, setMessage] = useState<string>('');

  const [errors, setErrors] = useState<{ name?: string; email?: string; message?: string }>({});
  const [submitted, setSubmitted] = useState<boolean>(false);

  const validateForm = () => {
    const newErrors: { name?: string; email?: string; message?: string } = {};
    if (!name.trim()) {
      newErrors.name = 'Please enter your name.';
    }
    if (!email.trim()) {
      newErrors.email = 'Please enter your email address.';
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      newErrors.email = 'Please enter a valid email address.';
    }
    if (!message.trim()) {
      newErrors.message = 'Please enter a message.';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const mailtoHref = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(
    `RALLY Contact — ${name || 'Inquiry'}`
  )}&body=${encodeURIComponent(`Name: ${name}\nEmail: ${email}\n\nMessage:\n${message}`)}`;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      setSubmitted(true);
      window.location.href = mailtoHref;
    }
  };

  return (
    <div className="bg-[#000000] text-white min-h-screen font-sans selection:bg-white/20 selection:text-white">
      {/* Global Navbar */}
      <Navbar />

      {/* 2. COMPACT HERO SECTION (~35–40vh) */}
      <section className="pt-20 pb-10 px-6 max-w-5xl mx-auto text-center flex flex-col items-center">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-white/[0.04] border border-white/10 text-[11px] font-mono tracking-[0.2em] text-white/70 uppercase mb-6"
        >
          <MessageSquare className="w-3.5 h-3.5 text-white/70" />
          CONTACT
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl font-medium tracking-tight text-white max-w-3xl leading-[1.08]"
        >
          Get in touch <br />
          <span className="font-serif italic font-normal text-white/90 tracking-normal">
            with the team.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-4 text-base sm:text-lg text-white/60 max-w-xl font-normal leading-relaxed"
        >
          Questions, feedback, or something not working right — we'd like to hear about it.
        </motion.p>
      </section>

      {/* 16. Subtle Visual Divider */}
      <div className="max-w-5xl mx-auto px-6">
        <hr className="border-white/10" />
      </div>

      {/* 3, 4, 5, 6. MAIN EDITORIAL TWO-COLUMN COMPOSITION (Overall width: 1050-1150px) */}
      <section className="max-w-[1120px] mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-[320px_1fr] lg:grid-cols-[340px_1fr] gap-12 lg:gap-16 items-start">
          
          {/* 4. LEFT SIDE: VERTICAL CONTACT INDEX (NOT CARDS!) */}
          <div className="font-mono text-xs space-y-8 pr-0 md:pr-4 relative">
            
            {/* 17. Subtle Animated Connectivity Indicator */}
            <div className="flex items-center gap-2 text-[11px] text-white/50 mb-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="uppercase tracking-widest font-bold text-white/70">CONNECTED TO TEAM</span>
            </div>

            {/* 01 EMAIL Entry */}
            <div className="space-y-2 border-b border-white/10 pb-6">
              <div className="text-[10px] text-white/40 tracking-[0.2em]">01</div>
              <div className="text-white font-bold text-sm tracking-wider uppercase">EMAIL</div>
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="text-white hover:text-white/80 transition-colors block font-sans text-base font-medium"
              >
                {CONTACT_EMAIL}
              </a>
              <p className="font-sans text-xs text-white/50 leading-relaxed pt-1">
                For questions, feedback, partnerships, or anything else.
              </p>
            </div>

            {/* 02 GITHUB Entry */}
            <div className="space-y-2 border-b border-white/10 pb-6">
              <div className="text-[10px] text-white/40 tracking-[0.2em]">02</div>
              <div className="text-white font-bold text-sm tracking-wider uppercase">GITHUB</div>
              <a
                href="https://github.com/keshavbanger/rally"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center justify-between text-white hover:text-white/80 transition-colors font-sans text-base font-medium"
              >
                <span>View project on GitHub</span>
                <ArrowRight className="w-4 h-4 text-white/40 group-hover:translate-x-1 group-hover:text-white transition-all" />
              </a>
              <p className="font-sans text-xs text-white/50 leading-relaxed pt-1">
                Follow development, report an issue, or contribute.
              </p>
            </div>

            {/* 03 RESPONSE Entry */}
            <div className="space-y-2">
              <div className="text-[10px] text-white/40 tracking-[0.2em]">03</div>
              <div className="text-white font-bold text-sm tracking-wider uppercase">RESPONSE</div>
              <p className="font-sans text-sm text-white/70 leading-relaxed">
                We read every message and respond directly to your inbox.
              </p>
            </div>

          </div>

          {/* 5. RIGHT SIDE: REDESIGNED CONTACT FORM */}
          <div className="max-w-[620px] w-full">
            {submitted ? (
              /* 12. SUCCESS STATE */
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="p-8 rounded-2xl bg-[#030303] border border-white/15 font-mono space-y-4 text-left"
              >
                <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-widest">
                  <CheckCircle2 className="w-4 h-4" /> MESSAGE READY
                </div>

                <h3 className="text-2xl font-sans font-medium text-white">
                  Opening your email client...
                </h3>

                <p className="font-sans text-sm text-white/60 leading-relaxed">
                  Your default email application is launching with your message pre-filled and addressed to <code className="text-white font-mono">{CONTACT_EMAIL}</code>.
                </p>

                <div className="pt-4">
                  <button
                    onClick={() => {
                      setSubmitted(false);
                      setName('');
                      setEmail('');
                      setMessage('');
                    }}
                    className="text-xs font-mono text-white/70 hover:text-white underline underline-offset-4"
                  >
                    Back to form
                  </button>
                </div>
              </motion.div>
            ) : (
              /* ACTIVE FORM */
              <motion.form
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                onSubmit={handleSubmit}
                className="space-y-6 font-sans"
                noValidate
              >
                {/* NAME FIELD */}
                <div className="space-y-2">
                  <label htmlFor="name" className="block text-xs font-mono text-white/50 uppercase tracking-widest">
                    NAME <span className="text-white/30">*</span>
                  </label>
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value);
                      if (errors.name) setErrors({ ...errors, name: undefined });
                    }}
                    placeholder="Your name"
                    className={`w-full bg-[#030303] text-white placeholder-white/30 px-4 py-3.5 rounded-xl border text-sm focus:outline-none transition-all ${
                      errors.name ? 'border-red-500/80 focus:border-red-500' : 'border-white/15 focus:border-white/40'
                    }`}
                  />
                  {errors.name && (
                    <div className="flex items-center gap-1.5 text-xs text-red-400 font-mono mt-1">
                      <AlertCircle className="w-3 h-3 shrink-0" />
                      <span>{errors.name}</span>
                    </div>
                  )}
                </div>

                {/* EMAIL FIELD */}
                <div className="space-y-2">
                  <label htmlFor="email" className="block text-xs font-mono text-white/50 uppercase tracking-widest">
                    EMAIL <span className="text-white/30">*</span>
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (errors.email) setErrors({ ...errors, email: undefined });
                    }}
                    placeholder="you@example.com"
                    className={`w-full bg-[#030303] text-white placeholder-white/30 px-4 py-3.5 rounded-xl border text-sm focus:outline-none transition-all ${
                      errors.email ? 'border-red-500/80 focus:border-red-500' : 'border-white/15 focus:border-white/40'
                    }`}
                  />
                  {errors.email && (
                    <div className="flex items-center gap-1.5 text-xs text-red-400 font-mono mt-1">
                      <AlertCircle className="w-3 h-3 shrink-0" />
                      <span>{errors.email}</span>
                    </div>
                  )}
                </div>

                {/* MESSAGE FIELD */}
                <div className="space-y-2">
                  <label htmlFor="message" className="block text-xs font-mono text-white/50 uppercase tracking-widest">
                    MESSAGE <span className="text-white/30">*</span>
                  </label>
                  <textarea
                    id="message"
                    value={message}
                    onChange={(e) => {
                      setMessage(e.target.value);
                      if (errors.message) setErrors({ ...errors, message: undefined });
                    }}
                    rows={6}
                    placeholder="What's on your mind?"
                    className={`w-full bg-[#030303] text-white placeholder-white/30 px-4 py-3.5 rounded-xl border text-sm focus:outline-none transition-all resize-y min-h-[150px] ${
                      errors.message ? 'border-red-500/80 focus:border-red-500' : 'border-white/15 focus:border-white/40'
                    }`}
                  />
                  {errors.message && (
                    <div className="flex items-center gap-1.5 text-xs text-red-400 font-mono mt-1">
                      <AlertCircle className="w-3 h-3 shrink-0" />
                      <span>{errors.message}</span>
                    </div>
                  )}
                </div>

                {/* 9 & 10. SUBMIT BUTTON & INTERACTION */}
                <div className="pt-2">
                  <button
                    type="submit"
                    className="group w-full sm:w-auto px-8 py-4 rounded-full bg-white text-black text-xs font-mono font-semibold tracking-wider uppercase flex items-center justify-center gap-3 hover:-translate-y-[1px] active:scale-[0.98] transition-all duration-200 shadow-[0_0_30px_rgba(255,255,255,0.15)] hover:shadow-[0_0_35px_rgba(255,255,255,0.3)]"
                  >
                    <span>Open in your email app</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </button>
                  
                  <p className="mt-3 text-[11px] font-mono text-white/40">
                    This opens a pre-filled email in your mail app — nothing is sent from this page directly.
                  </p>
                </div>

                {/* 15. Small Footer-Style Metadata Line */}
                <div className="pt-6 border-t border-white/10 flex items-center justify-between font-mono text-[10px] text-white/30 uppercase tracking-widest">
                  <span>HELLO@JOINRALLY.APP</span>
                  <span>RALLY ECOSYSTEM</span>
                </div>
              </motion.form>
            )}
          </div>

        </div>
      </section>

      {/* 18. MINIMAL PAGE FOOTER */}
      <footer className="py-12 border-t border-white/10 text-center font-mono text-xs text-white/40">
        <div className="max-w-4xl mx-auto px-6 space-y-4">
          <div className="text-white font-bold text-sm tracking-widest">RALLY</div>
          <p className="text-white/50 text-xs">Build trips together.</p>
          <div className="flex flex-wrap items-center justify-center gap-6 pt-2 text-[11px]">
            <Link href="/" className="hover:text-white transition-colors">Home</Link>
            <Link href="/product/live-tracking" className="hover:text-white transition-colors">Product</Link>
            <Link href="/safety" className="hover:text-white transition-colors">Safety</Link>
            <Link href="/docs/getting-started" className="hover:text-white transition-colors">Resources</Link>
            <Link href="/contact" className="text-white font-bold">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
