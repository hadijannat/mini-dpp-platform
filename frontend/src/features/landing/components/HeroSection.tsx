import { ArrowRight, CheckCircle2, ExternalLink, FlaskConical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { landingContent } from '../content/landingContent';
import DppCompactModel from './DppCompactModel';

function openHref(href: string) {
  if (href.startsWith('#')) {
    document.getElementById(href.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  if (href.startsWith('http://') || href.startsWith('https://')) {
    window.open(href, '_blank', 'noopener,noreferrer');
    return;
  }

  window.location.assign(href);
}

export default function HeroSection() {
  return (
    <section className="relative overflow-hidden px-4 pb-10 pt-12 sm:px-6 sm:pb-12 sm:pt-16 lg:px-8">
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-90"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(1100px 560px at 7% 8%, hsl(var(--landing-accent-cyan) / 0.2), transparent 62%), radial-gradient(980px 500px at 93% 0%, hsl(var(--landing-accent-amber) / 0.15), transparent 60%), linear-gradient(180deg, hsl(var(--landing-surface-0)) 0%, hsl(var(--landing-surface-1)) 100%)',
        }}
      />

      <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1.06fr_0.94fr] lg:items-start">
        <div className="rounded-3xl border border-landing-cyan/22 bg-white/82 p-6 shadow-[0_30px_50px_-38px_rgba(12,36,49,0.8)] backdrop-blur sm:p-8">
          <p className="landing-kicker inline-flex items-center rounded-full border border-landing-cyan/28 bg-landing-cyan/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-landing-cyan">
            {landingContent.hero.eyebrow}
          </p>

          <h1 className="mt-5 max-w-4xl font-display text-4xl font-semibold leading-tight tracking-tight text-landing-ink sm:text-5xl lg:text-6xl">
            {landingContent.hero.title}
          </h1>

          <p className="mt-5 max-w-2xl text-base leading-relaxed text-landing-muted sm:text-lg">
            {landingContent.hero.subtitle}
          </p>

          <div className="mt-5 flex flex-wrap gap-2.5">
            {landingContent.hero.proofPills.map((pill) => (
              <span
                key={pill}
                className="inline-flex rounded-full border border-landing-ink/14 bg-landing-surface-0/78 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-landing-ink"
              >
                {pill}
              </span>
            ))}
          </div>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
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
              className="h-12 rounded-full border-landing-ink/24 bg-white/70 px-6 text-sm font-semibold text-landing-ink backdrop-blur transition-colors hover:bg-white"
              onClick={() => openHref(landingContent.hero.secondaryCtaHref)}
              data-testid="landing-hero-secondary-cta"
            >
              {landingContent.hero.secondaryCta}
              <FlaskConical className="h-4 w-4" />
            </Button>
          </div>

          <a
            href={landingContent.hero.technicalEvidence.href}
            target={landingContent.hero.technicalEvidence.href.startsWith('http') ? '_blank' : undefined}
            rel={landingContent.hero.technicalEvidence.href.startsWith('http') ? 'noopener noreferrer' : undefined}
            className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            {landingContent.hero.technicalEvidence.label}
          </a>
        </div>

        <aside className="landing-panel rounded-3xl border border-landing-ink/14 bg-white/88 p-5 shadow-[0_30px_50px_-38px_rgba(12,36,49,0.8)] backdrop-blur sm:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
            Proof panel for technical and business review
          </p>
          <div className="mt-4 grid gap-3">
            {landingContent.hero.trustBullets.map((bullet) => (
              <div key={bullet} className="flex items-start gap-2.5 rounded-xl border border-landing-ink/10 bg-landing-surface-0/72 p-3 text-sm leading-relaxed text-landing-muted">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-landing-cyan" />
                <span>{bullet}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-landing-ink/12 bg-white/80 p-3.5 sm:p-4">
            <DppCompactModel />
          </div>
        </aside>
      </div>
    </section>
  );
}
