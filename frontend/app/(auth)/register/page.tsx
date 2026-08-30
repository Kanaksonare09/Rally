'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Chrome, Github, ArrowRight, AlertCircle, MailCheck } from 'lucide-react';
import AuthHero from '@/components/auth/AuthHero';
import SocialButton from '@/components/auth/SocialButton';
import AuthInput from '@/components/auth/AuthInput';
import { useAuth } from '@/lib/auth/AuthProvider';
import { getSupabaseClient } from '@/lib/supabase/client';

const STEPS = [
  { number: 1, text: 'Create your account' },
  { number: 2, text: 'Create or join a Rally' },
  { number: 3, text: 'Track your journey live' },
];

export default function RegisterPage() {
  const router = useRouter();
  const { signUpWithPassword } = useAuth();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkEmail, setCheckEmail] = useState(false);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    const fullName = [firstName, lastName].filter(Boolean).join(' ').trim() || undefined;
    const { error: signUpError } = await signUpWithPassword(email, password, fullName);
    setLoading(false);
    if (signUpError) {
      setError(signUpError);
      return;
    }
    // Supabase requires email confirmation by default — a session isn't
    // guaranteed to exist immediately after signUp(). If one was
    // returned (confirmation disabled on this project), go straight in;
    // otherwise tell the user to check their inbox rather than pretend
    // they're already signed in.
    const { data } = await getSupabaseClient().auth.getSession();
    if (data.session) {
      router.push('/create-group');
    } else {
      setCheckEmail(true);
    }
  };

  const handleOAuth = async (provider: 'google' | 'github') => {
    setError(null);
    const { error: oauthError } = await getSupabaseClient().auth.signInWithOAuth({
      provider,
      options: { redirectTo: typeof window !== 'undefined' ? `${window.location.origin}/create-group` : undefined },
    });
    if (oauthError) setError(oauthError.message);
  };

  return (
    <main className="flex min-h-screen w-full bg-background selection:bg-white/30 p-2 lg:h-screen lg:overflow-hidden lg:p-4 transition-all duration-500">
      <AuthHero
        heading="Join RALLY"
        subtitle="Follow these steps to get your group moving."
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

          {checkEmail ? (
            <div className="text-center space-y-4 py-6">
              <div className="w-14 h-14 rounded-full bg-rally-blue/10 border border-rally-blue/30 flex items-center justify-center mx-auto text-rally-blue">
                <MailCheck className="w-7 h-7" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-foreground">Check your email</h1>
                <p className="text-sm text-muted-foreground mt-1.5 max-w-sm mx-auto">
                  We sent a confirmation link to {email}. Follow it to finish creating your account, then sign in.
                </p>
              </div>
              <Link href="/login" className="inline-block font-semibold text-rally-blue hover:underline text-sm">
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <div>
                <h2 className="text-3xl font-medium tracking-tight text-foreground">Create your account</h2>
                <p className="text-muted-foreground text-sm mt-1.5">Set up your profile to start or join a Rally.</p>
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
                <div className="grid grid-cols-2 gap-4">
                  <AuthInput label="First Name" value={firstName} onChange={setFirstName} placeholder="Alex" required />
                  <AuthInput label="Last Name" value={lastName} onChange={setLastName} placeholder="Rivera" required />
                </div>
                <AuthInput label="Email" type="email" value={email} onChange={setEmail} placeholder="alex@rally.app" required />
                <AuthInput
                  label="Password"
                  type="password"
                  value={password}
                  onChange={setPassword}
                  placeholder="••••••••"
                  required
                  helperText="Requires at least 8 characters."
                />

                {error && (
                  <p className="flex items-center gap-1.5 text-xs text-red-400 px-1">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full h-14 bg-foreground text-background font-semibold rounded-full hover:bg-white/90 active:scale-[0.98] transition-all mt-4 flex items-center justify-center gap-2 disabled:opacity-70"
                >
                  {loading ? 'Creating Account…' : 'Create Account'}
                  {!loading && <ArrowRight className="w-4 h-4" />}
                </button>
              </form>

              <p className="text-center text-sm text-muted-foreground">
                Already have an account?{' '}
                <Link href="/login" className="font-semibold text-foreground hover:underline">
                  Log in
                </Link>
              </p>
            </>
          )}
        </motion.div>
      </div>
    </main>
  );
}
