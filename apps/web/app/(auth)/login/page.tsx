'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Chrome, Github, ArrowRight } from 'lucide-react';
import AuthHero from '@/components/auth/AuthHero';
import SocialButton from '@/components/auth/SocialButton';
import AuthInput from '@/components/auth/AuthInput';

const STEPS = [
  { number: 1, text: 'Sign in to your account' },
  { number: 2, text: 'Open your live dashboard' },
  { number: 3, text: 'Pick up where you left off' },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('demo@rally.app');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (loading) return;
    setLoading(true);
    setTimeout(() => router.push('/dashboard'), 600);
  };

  return (
    <main className="flex min-h-screen w-full bg-background selection:bg-white/30 p-2 lg:h-screen lg:overflow-hidden lg:p-4 transition-all duration-500">
      <AuthHero
        heading="Welcome back"
        subtitle="Sign in to reconnect with your group."
        steps={STEPS}
        activeStep={1}
      />

      <div className="flex-1 flex flex-col items-center justify-center py-12 lg:py-6 px-4 sm:px-12 lg:px-16 xl:px-24 overflow-y-auto lg:overflow-hidden">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="w-full max-w-xl space-y-8 lg:space-y-6 sm:space-y-10"
        >
          <Link href="/" className="lg:hidden inline-flex items-center">
            <img src="/assets/rally-wordmark.png" alt="RALLY" className="h-10 w-auto mt-2" />
          </Link>

          <div>
            <h2 className="text-3xl font-medium tracking-tight text-foreground">Sign in</h2>
            <p className="text-muted-foreground text-sm mt-1.5">Enter your credentials to access your dashboard.</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <SocialButton icon={Chrome} label="Google" onClick={() => handleSubmit()} />
            <SocialButton icon={Github} label="Github" onClick={() => handleSubmit()} />
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-background px-4 text-xs font-medium text-muted-foreground uppercase tracking-widest">
                Or
              </span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <AuthInput label="Email" type="email" value={email} onChange={setEmail} placeholder="name@company.com" required />
            <AuthInput
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="••••••••"
              required
            />

            <button
              type="submit"
              disabled={loading}
              className="w-full h-14 bg-foreground text-background font-semibold rounded-full hover:bg-white/90 active:scale-[0.98] transition-all mt-4 flex items-center justify-center gap-2 disabled:opacity-70"
            >
              {loading ? 'Signing In…' : 'Sign In'}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="font-semibold text-foreground hover:underline">
              Create account
            </Link>
          </p>
        </motion.div>
      </div>
    </main>
  );
}
