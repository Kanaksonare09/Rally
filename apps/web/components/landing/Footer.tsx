import Link from 'next/link';

const COLUMNS = [
  {
    title: 'Product',
    links: [
      { label: 'Live Dashboard', href: '/dashboard' },
      { label: 'Create a Rally', href: '/create-group' },
      { label: 'Join a Rally', href: '/join-group' },
    ],
  },
  {
    title: 'Account',
    links: [
      { label: 'Sign in', href: '/login' },
      { label: 'Create account', href: '/register' },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="border-t border-border bg-background px-8 md:px-28 pt-16 pb-10">
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-12">
          <div className="max-w-xs">
            <img src="/assets/rally-wordmark.png" alt="RALLY" className="h-10 w-auto mb-1" />
            <p className="text-sm text-muted-foreground leading-relaxed">
              Group intelligence for safer movement.
            </p>
          </div>

          <div className="flex gap-16">
            {COLUMNS.map((col) => (
              <div key={col.title}>
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4">
                  {col.title}
                </h4>
                <ul className="space-y-2.5">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <Link
                        href={link.href}
                        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
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

        <div className="mt-16 pt-6 border-t border-border">
          <p className="text-xs text-muted-foreground">&copy; 2026 RALLY. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
