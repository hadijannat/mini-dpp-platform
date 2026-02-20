import { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Fingerprint, LogIn, Menu, PlayCircle, UserPlus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { landingContent } from '../content/landingContent';

export default function LandingHeader() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }

    const desktopMediaQuery = window.matchMedia('(min-width: 1280px)');
    const handleDesktopMedia = (event: MediaQueryListEvent | MediaQueryList) => {
      if (event.matches) {
        setMobileOpen(false);
      }
    };

    // Close any open mobile sheet when transitioning into desktop layout.
    handleDesktopMedia(desktopMediaQuery);

    const listener = (event: MediaQueryListEvent) => handleDesktopMedia(event);
    desktopMediaQuery.addEventListener('change', listener);
    return () => {
      desktopMediaQuery.removeEventListener('change', listener);
    };
  }, []);

  return (
    <motion.header
      className="sticky top-0 z-50 border-b border-landing-ink/10 bg-[hsl(var(--landing-surface-0)/0.84)] backdrop-blur-xl"
      data-mobile-open={mobileOpen ? 'true' : 'false'}
      initial={shouldReduceMotion ? false : { opacity: 0, y: -16 }}
      animate={shouldReduceMotion ? undefined : { opacity: 1, y: 0 }}
      transition={shouldReduceMotion ? undefined : { duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="landing-container flex items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:gap-6 lg:px-8">
        <a
          href="/"
          className="group inline-flex shrink-0 items-center gap-2 lg:pr-1"
          aria-label="DPP Platform home"
        >
          <span className="rounded-full border border-landing-cyan/30 bg-landing-cyan/10 p-1.5 text-landing-cyan transition-transform group-hover:scale-105">
            <Fingerprint className="h-4 w-4" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-display text-base font-semibold text-landing-ink">DPP Platform</span>
            <span className="whitespace-nowrap text-[11px] uppercase tracking-[0.08em] text-landing-muted">
              dpp-platform.dev
            </span>
          </span>
        </a>

        <div className="hidden min-w-0 flex-1 items-center justify-end gap-5 xl:flex">
          <nav className="min-w-0 items-center gap-4 2xl:gap-5 xl:flex">
            {landingContent.navigation.map((link) => (
              <a
                key={link.href}
                href={link.href}
                target={link.external ? '_blank' : undefined}
                rel={link.external ? 'noopener noreferrer' : undefined}
                className="whitespace-nowrap text-sm font-medium text-landing-muted transition-colors hover:text-landing-ink"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="h-6 w-px bg-landing-ink/15" aria-hidden="true" />

          <div className="shrink-0 items-center gap-2 xl:flex">
            <Button size="sm" variant="outline" className="landing-cta rounded-full px-3.5 2xl:px-4" asChild>
              <a href="#sample-passport">
                <PlayCircle className="landing-cta-icon h-4 w-4" />
                Open demo
              </a>
            </Button>
            <Button size="sm" variant="outline" className="landing-cta rounded-full px-3.5 2xl:px-4" asChild>
              <a href="/login?mode=register">
                <UserPlus className="landing-cta-icon h-4 w-4" />
                Create account
              </a>
            </Button>
            <Button size="sm" className="landing-cta rounded-full px-3.5 2xl:px-4" asChild>
              <a href="/login">
                <LogIn className="landing-cta-icon h-4 w-4" />
                Sign in
              </a>
            </Button>
          </div>
        </div>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="text-landing-ink xl:hidden">
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
              <SheetDescription className="sr-only">
                Main site navigation and account actions
              </SheetDescription>
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
                <Button className="landing-cta mb-2 w-full rounded-full" size="sm" variant="outline" asChild>
                  <a href="#sample-passport" onClick={() => setMobileOpen(false)}>
                    <PlayCircle className="landing-cta-icon h-4 w-4" />
                    Open demo
                  </a>
                </Button>
                <Button className="landing-cta mb-2 w-full rounded-full" size="sm" variant="outline" asChild>
                  <a href="/login?mode=register" onClick={() => setMobileOpen(false)}>
                    <UserPlus className="landing-cta-icon h-4 w-4" />
                    Create account
                  </a>
                </Button>
                <Button className="landing-cta w-full rounded-full" size="sm" asChild>
                  <a href="/login" onClick={() => setMobileOpen(false)}>
                    <LogIn className="landing-cta-icon h-4 w-4" />
                    Sign in
                  </a>
                </Button>
              </div>
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </motion.header>
  );
}
