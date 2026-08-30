'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Chrome, Github, ArrowRight, AlertCircle } from 'lucide-react';
import AuthHero from '@/components/auth/AuthHero';
import SocialButton from '@/components/auth/SocialButton';
import AuthInput from '@/components/auth/AuthInput';
import { useAuth } from '@/lib/auth/AuthProvider';
import { getSupabaseClient } from '@/lib/supabase/client';

const STEPS = [
  { number: 1, text: 'Sign in to your account' },
  { number: 2, text: 'Open your live dashboard' },
  { number: 3, text: 'Pick up where you left off' },
];

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signInWithPassword, user } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signedIn, setSignedIn] = useState(false);

  const redirectTo = searchParams.get('redirect') || '/dashboard';

  // Navigate only once this component has actually re-rendered with a
  // truthy `user` from context, rather than immediately after
  // signInWithPassword's promise resolves. AuthProvider's own state
  // update (from that same call) and this navigation are otherwise two
  // independent async continuations with no guaranteed order — pushing
  // straight to router.push() could land on /dashboard a render tick
  // before the auth context has actually caught up, and RequireAuth
  // would bounce straight back to /login. Waiting for `user` here closes
  // that gap for good, regardless of timing.
  useEffect(() => {
    if (signedIn && user) {
      router.push(redirectTo);
    }
  }, [signedIn, user, router, redirectTo]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    const { error: signInError } = await signInWithPassword(email, password);
    setLoading(false);
    if (signInError) {
      setError(signInError);
      return;
    }
    setSignedIn(true);
  };

  const handleOAuth = async (provider: 'google' | 'github') => {
    setError(null);
    const { error: oauthError } = await getSupabaseClient().auth.signInWithOAuth({
      provider,
      options: { redirectTo: typeof window !== 'undefined' ? `${window.location.origin}${redirectTo}` : undefined },
    });
    if (oauthError) setError(oauthError.message);
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
            <img
              src="/assets/new-rally-logo-transparent.png"
              alt="RALLY"
              className="h-7.5 w-auto object-contain opacity-90 hover:opacity-100 transition-opacity"
            />
          </Link>

          <div>
            <h2 className="text-3xl font-medium tracking-tight text-foreground">Sign in</h2>
            <p className="text-muted-foreground text-sm mt-1.5">Enter your credentials to access your dashboard.</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <SocialButton icon={Chrome} label="Google" onClick={() => handleOAuth('google')} />
            <SocialButton icon={Github} label="Github" onClick={() => handleOAuth('github')} />
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

            {error && (
              <p className="flex items-center gap-1.5 text-xs text-red-400 px-1">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || signedIn}
              className="w-full h-14 bg-foreground text-background font-semibold rounded-full hover:bg-white/90 active:scale-[0.98] transition-all mt-4 flex items-center justify-center gap-2 disabled:opacity-70"
            >
              {loading || signedIn ? 'Signing In…' : 'Sign In'}
              {!loading && !signedIn && <ArrowRight className="w-4 h-4" />}
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
