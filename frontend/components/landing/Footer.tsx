import Link from 'next/link';
import { Twitter, Github, Linkedin, Youtube } from 'lucide-react';

const COLUMNS = [
  {
    title: 'Product',
    links: [
      { label: 'Live Tracking', href: '/dashboard' },
      { label: 'Geofencing', href: '/dashboard' },
      { label: 'Telemetry', href: '/dashboard' },
      { label: 'Safety Alerts', href: '/dashboard' },
      { label: 'Groups', href: '/join-group' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'Documentation', href: '#' },
      { label: 'Status', href: '#' },
      { label: 'API Reference', href: '#' },
      { label: 'Security', href: '#' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About', href: '#' },
      { label: 'Blog', href: '#' },
      { label: 'Careers', href: '#' },
      { label: 'Press', href: '#' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { label: 'Privacy Policy', href: '#' },
      { label: 'Terms of Service', href: '#' },
      { label: 'Cookie Policy', href: '#' },
      { label: 'GDPR', href: '#' },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="relative bg-[#000000] overflow-hidden pt-12 pb-24 border-t border-white/[0.05]">
      {/* Huge subtle text background */}
      <div 
        className="absolute top-0 left-1/2 -translate-x-1/2 w-full flex justify-center pointer-events-none select-none overflow-hidden"
        style={{ maskImage: 'linear-gradient(to bottom, black 20%, transparent 100%)', WebkitMaskImage: 'linear-gradient(to bottom, black 20%, transparent 100%)' }}
      >
        <h1 className="text-[26vw] leading-[0.8] font-bold tracking-tighter uppercase whitespace-nowrap text-white/[0.03]">
          RALLY
        </h1>
      </div>

      <div className="relative z-10 max-w-[1280px] mx-auto px-6 md:px-8 mt-[15vw]">
        <div className="flex flex-col lg:flex-row justify-between gap-16 lg:gap-8">
          {/* Left section */}
          <div className="flex flex-col gap-8 max-w-[280px]">
            <div className="text-[13px] leading-relaxed text-white/50">
              <p>2261 Market Street #5039</p>
              <p>San Francisco, CA 94114</p>
            </div>

            <div className="flex items-center gap-3">
              <a href="#" className="w-[34px] h-[34px] rounded-full border border-white/10 flex items-center justify-center text-white/50 hover:text-white hover:border-white/30 hover:bg-white/5 transition-all">
                <Twitter className="w-[15px] h-[15px]" />
              </a>
              <a href="#" className="w-[34px] h-[34px] rounded-full border border-white/10 flex items-center justify-center text-white/50 hover:text-white hover:border-white/30 hover:bg-white/5 transition-all">
                <Github className="w-[15px] h-[15px]" />
              </a>
              <a href="#" className="w-[34px] h-[34px] rounded-full border border-white/10 flex items-center justify-center text-white/50 hover:text-white hover:border-white/30 hover:bg-white/5 transition-all">
                <Linkedin className="w-[15px] h-[15px]" />
              </a>
              <a href="#" className="w-[34px] h-[34px] rounded-full border border-white/10 flex items-center justify-center text-white/50 hover:text-white hover:border-white/30 hover:bg-white/5 transition-all">
                <Youtube className="w-[15px] h-[15px]" />
              </a>
            </div>

            <div className="inline-flex items-center gap-2.5 px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.02] w-fit hover:bg-white/[0.05] transition-colors cursor-pointer">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-60"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-[13px] text-white/70 font-medium tracking-wide">All systems operational</span>
            </div>
          </div>

          {/* Right section columns */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-12 gap-y-12 lg:gap-x-20">
            {COLUMNS.map((col) => (
              <div key={col.title} className="flex flex-col gap-6">
                <h4 className="text-[14px] font-medium text-white/90">
                  {col.title}
                </h4>
                <ul className="flex flex-col gap-4">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <Link
                        href={link.href}
                        className="text-[14px] text-white/50 hover:text-white transition-colors"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
