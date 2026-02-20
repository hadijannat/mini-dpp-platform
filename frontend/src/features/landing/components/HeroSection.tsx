import { motion, useReducedMotion } from 'framer-motion';
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

const heroEase = [0.22, 1, 0.36, 1] as const;

export default function HeroSection() {
  const shouldReduceMotion = useReducedMotion();

  const stagger = shouldReduceMotion
    ? undefined
    : {
        hidden: {},
        visible: {
          transition: {
            staggerChildren: 0.07,
          },
        },
      };

  const childMotion = shouldReduceMotion
    ? {}
    : {
        variants: {
          hidden: { opacity: 0, y: 20 },
          visible: { opacity: 1, y: 0 },
        },
        transition: { duration: 0.45, ease: heroEase },
      };

  return (
    <section className="relative overflow-hidden px-4 pb-10 pt-12 sm:px-6 sm:pb-12 sm:pt-16 lg:px-8 lg:pb-16 lg:pt-20">
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-90"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(1240px 560px at 12% 8%, hsl(var(--landing-accent-cyan) / 0.26), transparent 65%), radial-gradient(1080px 520px at 92% 3%, hsl(var(--landing-accent-amber) / 0.23), transparent 66%), linear-gradient(180deg, hsl(var(--landing-paper)) 0%, hsl(var(--landing-surface)) 100%)',
        }}
      />

      <div className="landing-container">
        <motion.div
          className="text-center"
          variants={stagger}
          initial={shouldReduceMotion ? false : 'hidden'}
          animate={shouldReduceMotion ? undefined : 'visible'}
        >
          <motion.p
            className="landing-kicker inline-flex rounded-full border border-landing-cyan/30 bg-landing-cyan/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-landing-cyan"
            {...childMotion}
          >
            {landingContent.hero.eyebrow}
          </motion.p>

          <motion.h1 className="landing-hero-title mx-auto mt-7 max-w-5xl font-display text-landing-ink" {...childMotion}>
            {landingContent.hero.title}
          </motion.h1>

          <motion.p className="landing-lead mx-auto mt-6 max-w-3xl text-landing-muted" {...childMotion}>
            {landingContent.hero.subtitle}
          </motion.p>

          <motion.div className="mt-6 flex flex-wrap justify-center gap-2.5" {...childMotion}>
            {landingContent.hero.proofPills.map((pill) => (
              <span
                key={pill}
                className="inline-flex rounded-full border border-landing-ink/15 bg-white/90 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-landing-ink"
              >
                {pill}
              </span>
            ))}
          </motion.div>

          <motion.div className="mt-9 flex flex-col items-center gap-3 sm:flex-row sm:justify-center" {...childMotion}>
            <Button
              className="landing-cta h-12 rounded-full px-7 text-sm font-semibold"
              onClick={() => openHref(landingContent.hero.primaryCtaHref)}
              data-testid="landing-hero-primary-cta"
            >
              {landingContent.hero.primaryCta}
              <ArrowRight className="landing-cta-icon h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              className="landing-cta h-12 rounded-full border-landing-ink/25 bg-white/80 px-7 text-sm font-semibold text-landing-ink backdrop-blur"
              onClick={() => openHref(landingContent.hero.secondaryCtaHref)}
              data-testid="landing-hero-secondary-cta"
            >
              {landingContent.hero.secondaryCta}
              <ExternalLink className="landing-cta-icon h-4 w-4" />
            </Button>
          </motion.div>
        </motion.div>

        <motion.div
          className="landing-panel landing-panel-premium mx-auto mt-10 max-w-landing p-6 sm:p-7"
          initial={shouldReduceMotion ? false : { opacity: 0, y: 20, scale: 0.97 }}
          animate={shouldReduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
          transition={shouldReduceMotion ? undefined : { duration: 0.55, ease: heroEase, delay: 0.12 }}
        >
          <DppCompactModel />

          <div className="mt-5 grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
            {landingContent.hero.trustBullets.map((bullet) => (
              <div key={bullet} className="flex items-start gap-2 text-sm leading-relaxed text-landing-muted">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-landing-cyan" />
                <span>{bullet}</span>
              </div>
            ))}
          </div>

          <div className="mt-5 text-center">
            <a
              href={landingContent.hero.technicalEvidence.href}
              target={landingContent.hero.technicalEvidence.href.startsWith('http') ? '_blank' : undefined}
              rel={landingContent.hero.technicalEvidence.href.startsWith('http') ? 'noopener noreferrer' : undefined}
              className="landing-cta inline-flex items-center gap-2 text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
            >
              <ExternalLink className="landing-cta-icon h-3.5 w-3.5" />
              {landingContent.hero.technicalEvidence.label}
            </a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
