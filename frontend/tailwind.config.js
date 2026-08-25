/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // New landing-page design system (HSL CSS vars, see globals.css)
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        'muted-foreground': 'hsl(var(--muted-foreground))',
        card: 'hsl(var(--card))',
        border: 'hsl(var(--border))',

        // Legacy tokens — still referenced by /login, /register.
        // Kept flat (not swapped to CSS vars) so those pages don't shift.
        'card-border': 'rgba(255, 255, 255, 0.12)',
        'surface-dark': '#28282A',
        'rally-blue': {
          DEFAULT: '#19BFFF',
          secondary: '#1688FF',
          glow: 'rgba(25, 191, 255, 0.25)',
        },
        'rally-text': {
          primary: '#FFFFFF',
          secondary: '#C8C8C8',
          muted: '#8E8E8E',
        },
        success: '#22C55E',
        warning: '#F59E0B',
        danger: '#EF4444',
      },
      boxShadow: {
        'blue-glow': '0 0 30px rgba(25, 191, 255, 0.25)',
        'blue-glow-lg': '0 0 60px rgba(25, 191, 255, 0.2), 0 0 140px rgba(25, 191, 255, 0.1)',
        'card': '0 12px 40px rgba(0, 0, 0, 0.8)',
        'card-hover': '0 20px 50px rgba(0, 0, 0, 0.9)',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', '-apple-system', 'sans-serif'],
        serif: ['var(--font-instrument-serif)', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        'hero': ['4.5rem', { lineHeight: '1.05', letterSpacing: '-0.03em', fontWeight: '500' }],
        'hero-sm': ['2.75rem', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '500' }],
        'display': ['3.5rem', { lineHeight: '1.1', letterSpacing: '-0.025em', fontWeight: '500' }],
        'display-sm': ['2.25rem', { lineHeight: '1.15', letterSpacing: '-0.02em', fontWeight: '500' }],
      },
      maxWidth: {
        'content': '1280px',
      },
      animation: {
        'pulse-subtle': 'pulse-subtle 3s ease-in-out infinite',
        'float': 'float 4s ease-in-out infinite',
        'live-pulse': 'live-pulse 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
