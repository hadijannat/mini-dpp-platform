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

    const desktopMediaQuery = window.matchMedia('(min-width: 1536px)');
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
      className="sticky top-0 z-50 border-b border-landing-ink/10 bg-[linear-gradient(180deg,hsl(var(--landing-surface-0)/0.96),hsl(var(--landing-surface-0)/0.88))] shadow-[0_16px_36px_-28px_rgba(8,30,44,0.75)] backdrop-blur-xl"
      data-mobile-open={mobileOpen ? 'true' : 'false'}
      initial={shouldReduceMotion ? false : { opacity: 0, y: -16 }}
      animate={shouldReduceMotion ? undefined : { opacity: 1, y: 0 }}
      transition={shouldReduceMotion ? undefined : { duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="mx-auto flex w-full max-w-[94rem] items-center justify-between gap-4 px-4 py-2.5 sm:px-6 lg:gap-5 lg:px-8">
        <a
          href="/"
          className="group inline-flex shrink-0 items-center gap-2.5 rounded-full border border-transparent pr-1 transition-colors hover:border-landing-ink/10"
          aria-label="DPP Platform home"
        >
          <span className="rounded-full border border-landing-cyan/30 bg-landing-cyan/10 p-1.5 text-landing-cyan shadow-[inset_0_0_0_1px_rgba(255,255,255,0.35)] transition-transform group-hover:scale-105">
            <Fingerprint className="h-[17px] w-[17px]" />
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-display text-[1.02rem] font-semibold text-landing-ink">DPP Platform</span>
            <span className="whitespace-nowrap text-[11px] uppercase tracking-[0.11em] text-landing-muted">
              dpp-platform.dev
            </span>
          </span>
        </a>

        <div className="hidden min-w-0 flex-1 items-center justify-end gap-3 2xl:flex">
          <nav className="min-w-0 items-center gap-0.5 rounded-full border border-landing-ink/12 bg-white/62 p-1 shadow-[0_14px_28px_-24px_rgba(10,36,52,0.6)] 2xl:flex">
            {landingContent.navigation.map((link) => (
              <a
                key={link.href}
                href={link.href}
                target={link.external ? '_blank' : undefined}
                rel={link.external ? 'noopener noreferrer' : undefined}
                className="whitespace-nowrap rounded-full px-2.5 py-1.5 text-sm font-medium text-landing-muted transition-colors hover:bg-white hover:text-landing-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-landing-cyan/40"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="shrink-0 items-center gap-1.5 rounded-full border border-landing-ink/12 bg-white/62 p-1 shadow-[0_14px_28px_-24px_rgba(10,36,52,0.6)] 2xl:flex">
            <Button
              size="sm"
              variant="outline"
              className="landing-cta h-9 rounded-full border-landing-ink/18 bg-white/75 px-3 text-landing-ink hover:bg-white 2xl:px-3.5"
              asChild
            >
              <a href="#sample-passport">
                <PlayCircle className="landing-cta-icon h-4 w-4" />
                Open demo
              </a>
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="landing-cta h-9 rounded-full border-landing-ink/18 bg-white/75 px-3 text-landing-ink hover:bg-white 2xl:px-3.5"
              asChild
            >
              <a href="/login?mode=register">
                <UserPlus className="landing-cta-icon h-4 w-4" />
                Create account
              </a>
            </Button>
            <Button size="sm" className="landing-cta h-9 rounded-full px-3 2xl:px-3.5" asChild>
              <a href="/login">
                <LogIn className="landing-cta-icon h-4 w-4" />
                Sign in
              </a>
            </Button>
          </div>
        </div>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="rounded-full border border-landing-ink/12 bg-white/75 text-landing-ink hover:bg-white 2xl:hidden"
            >
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
                  className="rounded-xl border border-transparent px-3 py-2 text-sm font-medium text-landing-muted transition-colors hover:border-landing-ink/12 hover:bg-white hover:text-landing-ink"
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
