'use client';

import Link from 'next/link';
import { ChevronDown } from 'lucide-react';

const NAV_LINKS = [
  { label: 'Home', href: '#' },
  { label: 'Product', href: '#', hasChevron: true },
  { label: 'Reviews', href: '#testimonial' },
  { label: 'Contact us', href: '#' },
];

export default function Navbar() {
  return (
    <nav className="relative z-40 flex items-center justify-between px-8 md:px-28 py-4">
      <div className="flex items-center gap-12 md:gap-20">
        <Link href="/" className="flex items-center" aria-label="RALLY Home">
          <img src="/assets/rally-wordmark.png" alt="RALLY" className="h-6 w-auto" />
        </Link>

        <div className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="inline-flex items-center gap-1 px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              {link.label}
              {link.hasChevron && <ChevronDown className="w-3.5 h-3.5" />}
            </a>
          ))}
        </div>
      </div>

      <Link
        href="/login"
        className="bg-foreground text-background rounded-lg text-sm font-semibold px-5 py-2 hover:opacity-85 transition-opacity"
      >
        Sign In
      </Link>
    </nav>
  );
}
