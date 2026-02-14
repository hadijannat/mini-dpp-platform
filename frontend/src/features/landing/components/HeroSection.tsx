import { ArrowRight, CheckCircle2, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { landingContent } from '../content/landingContent';
import DppCompactModel from './DppCompactModel';

function openHref(href: string) {
  if (href.startsWith('#')) {
    document.getElementById(href.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  window.open(href, '_blank', 'noopener,noreferrer');
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
        {/* ── Hero text block ── */}
        <div className="text-center">
          <p className="landing-kicker inline-flex items-center rounded-full border border-landing-cyan/30 bg-landing-cyan/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-landing-cyan">
            {landingContent.hero.eyebrow}
          </p>

          <h1 className="mx-auto mt-6 max-w-4xl font-display text-4xl font-semibold leading-tight tracking-tight text-landing-ink sm:text-5xl lg:text-6xl">
            {landingContent.hero.title}
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-landing-muted sm:text-lg">
            {landingContent.hero.subtitle}
          </p>

          <div className="mt-5 flex flex-wrap justify-center gap-2.5">
            {landingContent.hero.proofPills.map((pill) => (
              <span
                key={pill}
                className="inline-flex rounded-full border border-landing-ink/15 bg-white/80 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-landing-ink"
              >
                {pill}
              </span>
            ))}
          </div>

          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Button
              className="h-12 rounded-full px-6 text-sm font-semibold"
              onClick={() => openHref(landingContent.hero.primaryCtaHref)}
              data-testid="landing-hero-primary-cta"
            >
              {landingContent.hero.primaryCta}
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              className="h-12 rounded-full border-landing-ink/25 bg-white/70 px-6 text-sm font-semibold text-landing-ink backdrop-blur transition-colors hover:bg-white"
              onClick={() => openHref(landingContent.hero.secondaryCtaHref)}
              data-testid="landing-hero-secondary-cta"
            >
              {landingContent.hero.secondaryCta}
              <ExternalLink className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* ── Full-width AAS model ── */}
        <div className="landing-panel mx-auto mt-10 max-w-4xl rounded-3xl border border-landing-cyan/25 bg-white/85 p-6 shadow-[0_24px_48px_-36px_rgba(20,44,55,0.45)] backdrop-blur">
          <DppCompactModel />

          <div className="mt-5 grid gap-x-6 gap-y-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {landingContent.hero.trustBullets.map((bullet) => (
              <div key={bullet} className="flex items-start gap-2 text-sm leading-relaxed text-landing-muted">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-landing-cyan" />
                <span>{bullet}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 text-center">
            <a
              href={landingContent.hero.technicalEvidence.href}
              target={landingContent.hero.technicalEvidence.href.startsWith('http') ? '_blank' : undefined}
              rel={landingContent.hero.technicalEvidence.href.startsWith('http') ? 'noopener noreferrer' : undefined}
              className="inline-flex items-center gap-2 text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {landingContent.hero.technicalEvidence.label}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
