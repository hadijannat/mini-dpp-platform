import type { ComponentType } from 'react';
import { Factory, ScanLine, Scale, Wrench } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import type { LandingIconKey } from '../content/landingContent';
import { landingContent } from '../content/landingContent';

const iconByKey: Record<LandingIconKey, ComponentType<{ className?: string }>> = {
  factory: Factory,
  scale: Scale,
  wrench: Wrench,
  scan: ScanLine,
  workflow: Factory,
  shield: Scale,
  globe: ScanLine,
  api: Wrench,
};

export default function AudienceSegmentsSection() {
  const shouldReduceMotion = useReducedMotion();

  const cardVariants = shouldReduceMotion
    ? undefined
    : ({
        hidden: { opacity: 0, y: 24 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.5, ease: 'easeOut' as const },
        },
      } as const);

  return (
    <section id="audiences" className="scroll-mt-24 px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-10 max-w-3xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            Audience-first information architecture
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
            Communicate clearly to every stakeholder group
          </h2>
          <p className="mt-4 text-base leading-relaxed text-landing-muted sm:text-lg">
            The first page is designed to guide each audience through exactly the information they need,
            while preserving strong privacy defaults for sensitive record-level data.
          </p>
        </div>

        <motion.div
          className="grid gap-5 sm:grid-cols-2"
          initial={shouldReduceMotion ? undefined : 'hidden'}
          whileInView={shouldReduceMotion ? undefined : 'show'}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ staggerChildren: shouldReduceMotion ? 0 : 0.08 }}
        >
          {landingContent.audienceCards.map((segment) => {
            const Icon = iconByKey[segment.icon] ?? Factory;
            return (
              <motion.article
                key={segment.id}
                variants={cardVariants}
                className="landing-panel rounded-3xl border border-landing-ink/12 bg-white/75 p-6 shadow-[0_20px_52px_-40px_rgba(10,37,50,0.6)] backdrop-blur"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                      {segment.id}
                    </p>
                    <h3 className="mt-2 font-display text-2xl font-semibold text-landing-ink">
                      {segment.title}
                    </h3>
                  </div>
                  <span className="rounded-full border border-landing-cyan/25 bg-landing-cyan/10 p-2.5 text-landing-cyan">
                    <Icon className="h-5 w-5" />
                  </span>
                </div>

                <p className="mt-4 text-sm leading-relaxed text-landing-muted sm:text-base">
                  {segment.description}
                </p>

                <ul className="mt-5 space-y-2">
                  {segment.outcomes.map((outcome) => (
                    <li key={outcome} className="flex items-start gap-2 text-sm text-landing-ink">
                      <span
                        aria-hidden="true"
                        className="mt-[0.42rem] inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-landing-cyan"
                      />
                      <span>{outcome}</span>
                    </li>
                  ))}
                </ul>
              </motion.article>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
