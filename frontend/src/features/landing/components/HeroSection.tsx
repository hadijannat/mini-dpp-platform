import { ArrowRight, Sparkles } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import { useAuth } from 'react-oidc-context';
import { Button } from '@/components/ui/button';
import { landingContent } from '../content/landingContent';

export default function HeroSection() {
  const auth = useAuth();
  const shouldReduceMotion = useReducedMotion();

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: shouldReduceMotion ? 0 : 0.12,
      },
    },
  };

  const itemVariants = shouldReduceMotion
    ? undefined
    : ({
        hidden: { opacity: 0, y: 24 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.6, ease: 'easeOut' as const },
        },
      } as const);

  const handlePrimaryCta = () => auth.signinRedirect();
  const handleSecondaryCta = () => {
    document.getElementById('audiences')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <section className="relative overflow-hidden px-4 pb-20 pt-20 sm:px-6 sm:pb-24 sm:pt-24 lg:px-8">
      <div
        className="pointer-events-none absolute inset-0 -z-10 opacity-80"
        aria-hidden="true"
        style={{
          background:
            'radial-gradient(1200px 540px at 10% 15%, hsl(var(--landing-accent-cyan) / 0.18), transparent 62%), radial-gradient(900px 480px at 90% 0%, hsl(var(--landing-accent-amber) / 0.2), transparent 60%), linear-gradient(180deg, hsl(var(--landing-surface-0)) 0%, hsl(var(--landing-surface-1)) 72%)',
        }}
      />

      <motion.div
        className="mx-auto flex max-w-6xl flex-col gap-12"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
          <motion.div variants={itemVariants}>
            <p className="landing-kicker inline-flex items-center gap-2 rounded-full border border-landing-cyan/30 bg-landing-cyan/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-landing-cyan">
              <Sparkles className="h-3.5 w-3.5" />
              {landingContent.hero.eyebrow}
            </p>
            <h1 className="mt-6 font-display text-4xl font-semibold leading-tight tracking-tight text-landing-ink sm:text-5xl lg:text-6xl">
              {landingContent.hero.title}
              <span className="block text-landing-cyan">{landingContent.hero.emphasis}</span>
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-relaxed text-landing-muted sm:text-lg">
              {landingContent.hero.subtitle}
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Button
                className="h-12 rounded-full px-6 text-sm font-semibold"
                onClick={handlePrimaryCta}
                data-testid="landing-hero-primary-cta"
              >
                {landingContent.hero.primaryCta}
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="h-12 rounded-full border-landing-ink/25 bg-white/70 px-6 text-sm font-semibold text-landing-ink backdrop-blur transition-colors hover:bg-white"
                onClick={handleSecondaryCta}
              >
                {landingContent.hero.secondaryCta}
              </Button>
            </div>
          </motion.div>

          <motion.div
            variants={itemVariants}
            className="landing-panel relative overflow-hidden rounded-3xl border border-landing-cyan/25 bg-white/80 p-6 shadow-[0_28px_60px_-42px_rgba(20,44,55,0.55)] backdrop-blur"
          >
            <div
              className="pointer-events-none absolute right-0 top-0 h-36 w-36 rounded-bl-[44px]"
              aria-hidden="true"
              style={{
                background:
                  'linear-gradient(135deg, hsl(var(--landing-accent-cyan) / 0.24), hsl(var(--landing-accent-amber) / 0.16))',
              }}
            />
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
              Conversion focus
            </p>
            <h2 className="mt-3 font-display text-2xl font-semibold text-landing-ink sm:text-3xl">
              Guide each audience from trust to action
            </h2>
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
          </motion.div>
        </div>
      </motion.div>
    </section>
  );
}
