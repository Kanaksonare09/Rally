import type { Metadata } from 'next';
import { Inter, Instrument_Serif } from 'next/font/google';
import { Providers } from './providers';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-inter',
  display: 'swap',
});

const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  weight: ['400'],
  style: ['normal', 'italic'],
  variable: '--font-instrument-serif',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'RALLY — Real-Time Group Intelligence',
  description:
    'RALLY helps groups track location, safety, and progress with precision — real-time movement intelligence for safer journeys.',
  keywords: ['group intelligence', 'real-time movement', 'group safety', 'movement intelligence', 'separation detection', 'predictive risk'],
  openGraph: {
    title: 'RALLY — Real-Time Group Intelligence',
    description: 'Your group. One clear overview.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark scroll-smooth ${inter.variable} ${instrumentSerif.variable}`}>
      <body className="bg-background text-foreground min-h-screen antialiased font-sans selection:bg-white/20 selection:text-white">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
