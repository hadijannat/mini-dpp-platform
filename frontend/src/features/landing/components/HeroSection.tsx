import { ArrowRight, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { landingContent } from '../content/landingContent';

function scrollToSamplePassport() {
  document.getElementById('sample-passport')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function openQuickstart() {
  window.open(
    'https://github.com/hadijannat/mini-dpp-platform#quick-start-docker-compose',
    '_blank',
    'noopener,noreferrer',
  );
}

export default function HeroSection() {
  return (
    <section className="relative overflow-hidden px-4 pb-14 pt-20 sm:px-6 sm:pb-16 sm:pt-24 lg:px-8">
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-85"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(1200px 540px at 10% 15%, hsl(var(--landing-accent-cyan) / 0.18), transparent 62%), radial-gradient(900px 480px at 90% 0%, hsl(var(--landing-accent-amber) / 0.18), transparent 60%), linear-gradient(180deg, hsl(var(--landing-surface-0)) 0%, hsl(var(--landing-surface-1)) 72%)',
        }}
      />

      <div className="mx-auto max-w-6xl">
        <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-start">
          <div>
            <p className="landing-kicker inline-flex items-center rounded-full border border-landing-cyan/30 bg-landing-cyan/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-landing-cyan">
              {landingContent.hero.eyebrow}
            </p>

            <h1 className="mt-6 font-display text-4xl font-semibold leading-tight tracking-tight text-landing-ink sm:text-5xl lg:text-6xl">
              {landingContent.hero.title}
            </h1>

            <p className="mt-6 max-w-3xl text-base leading-relaxed text-landing-muted sm:text-lg">
              {landingContent.hero.subtitle}
            </p>

            <div className="mt-5 flex flex-wrap gap-2.5">
              {landingContent.hero.proofPills.map((pill) => (
                <span
                  key={pill}
                  className="inline-flex rounded-full border border-landing-ink/14 bg-white/80 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-landing-ink"
                >
                  {pill}
                </span>
              ))}
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Button
                className="h-12 rounded-full px-6 text-sm font-semibold"
                onClick={scrollToSamplePassport}
                data-testid="landing-hero-primary-cta"
              >
                {landingContent.hero.primaryCta}
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="h-12 rounded-full border-landing-ink/25 bg-white/70 px-6 text-sm font-semibold text-landing-ink backdrop-blur transition-colors hover:bg-white"
                onClick={openQuickstart}
                data-testid="landing-hero-secondary-cta"
              >
                {landingContent.hero.secondaryCta}
                <ExternalLink className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <aside className="landing-panel rounded-3xl border border-landing-cyan/25 bg-white/80 p-6 shadow-[0_28px_60px_-42px_rgba(20,44,55,0.55)] backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">Evidence</p>
            <ul className="mt-4 space-y-3">
              {landingContent.hero.evidenceLinks.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    target={link.href.startsWith('http') ? '_blank' : undefined}
                    rel={link.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                    className="inline-flex items-center gap-2 text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
            <ul className="mt-6 space-y-3">
              {landingContent.hero.highlights.map((highlight) => (
                <li
                  key={highlight}
                  className="rounded-2xl border border-landing-ink/10 bg-white/85 px-4 py-3 text-sm text-landing-muted"
                >
                  {highlight}
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </div>
    </section>
  );
}
