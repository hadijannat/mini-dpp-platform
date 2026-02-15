import { useState } from 'react';
import { Fingerprint, LogIn, Menu, PlayCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { landingContent } from '../content/landingContent';

export default function LandingHeader() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-landing-ink/10 bg-[hsl(var(--landing-surface-0)/0.84)] backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <a href="/" className="group inline-flex items-center gap-2" aria-label="DPP Platform home">
          <span className="rounded-full border border-landing-cyan/30 bg-landing-cyan/10 p-1.5 text-landing-cyan transition-transform group-hover:scale-105">
            <Fingerprint className="h-4 w-4" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-display text-base font-semibold text-landing-ink">DPP Platform</span>
            <span className="text-[11px] uppercase tracking-[0.12em] text-landing-muted">dpp-platform.dev</span>
          </span>
        </a>

        <nav className="hidden items-center gap-6 md:flex">
          {landingContent.navigation.map((link) => (
            <a
              key={link.href}
              href={link.href}
              target={link.external ? '_blank' : undefined}
              rel={link.external ? 'noopener noreferrer' : undefined}
              className="text-sm font-medium text-landing-muted transition-colors hover:text-landing-ink"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button size="sm" variant="outline" className="rounded-full px-4" asChild>
            <a href="#sample-passport">
              <PlayCircle className="h-4 w-4" />
              Open sample
            </a>
          </Button>
          <Button size="sm" className="rounded-full px-4" asChild>
            <a href="/login">
              <LogIn className="h-4 w-4" />
              Sign in
            </a>
          </Button>
        </div>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="text-landing-ink md:hidden">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Open menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent
            side="right"
            className="w-72 border-l border-landing-ink/12 bg-[hsl(var(--landing-surface-0))]"
          >
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2 font-display text-landing-ink">
                <Fingerprint className="h-5 w-5 text-landing-cyan" />
                DPP Platform
              </SheetTitle>
            </SheetHeader>

            <nav className="mt-8 flex flex-col gap-3">
              {landingContent.navigation.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  target={link.external ? '_blank' : undefined}
                  rel={link.external ? 'noopener noreferrer' : undefined}
                  onClick={() => setMobileOpen(false)}
                  className="rounded-xl border border-transparent px-3 py-2 text-sm font-medium text-landing-muted transition-colors hover:border-landing-ink/10 hover:bg-white hover:text-landing-ink"
                >
                  {link.label}
                </a>
              ))}

              <div className="mt-4 border-t border-landing-ink/10 pt-4">
                <Button className="mb-2 w-full rounded-full" size="sm" variant="outline" asChild>
                  <a href="#sample-passport" onClick={() => setMobileOpen(false)}>
                    <PlayCircle className="h-4 w-4" />
                    Open sample
                  </a>
                </Button>
                <Button className="w-full rounded-full" size="sm" asChild>
                  <a href="/login" onClick={() => setMobileOpen(false)}>
                    <LogIn className="h-4 w-4" />
                    Sign in
                  </a>
                </Button>
              </div>
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
