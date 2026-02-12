import type { ComponentType } from 'react';
import { Factory, ScanLine, Scale, Wrench } from 'lucide-react';
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
  return (
    <section id="audiences" className="scroll-mt-24 px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-10 max-w-3xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            Audience-first information architecture
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
            Speak each implementation dialect natively
          </h2>
          <p className="mt-4 text-base leading-relaxed text-landing-muted sm:text-lg">
            The first screen is tuned for AAS builders, DPP implementers, and dataspace teams while
            preserving strict public-data boundaries.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          {landingContent.audienceCards.map((segment) => {
            const Icon = iconByKey[segment.icon] ?? Factory;
            return (
              <article
                key={segment.id}
                className="landing-panel rounded-3xl border border-landing-ink/12 bg-white/75 p-6 shadow-[0_20px_52px_-40px_rgba(10,37,50,0.6)] backdrop-blur transition-transform duration-200 hover:-translate-y-0.5"
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
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
