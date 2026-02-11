import { Braces, Globe2, Route, ShieldCheck } from 'lucide-react';
import type { ComponentType } from 'react';
import { useAuth } from 'react-oidc-context';
import { Button } from '@/components/ui/button';
import AnimatedSection from './components/AnimatedSection';
import AudienceSegmentsSection from './components/AudienceSegmentsSection';
import DataExposureSection from './components/DataExposureSection';
import HeroSection from './components/HeroSection';
import LandingFooter from './components/LandingFooter';
import LandingHeader from './components/LandingHeader';
import LandingMetricsSection from './components/LandingMetricsSection';
import type { LandingIconKey } from './content/landingContent';
import { landingContent } from './content/landingContent';

const capabilityIcons: Record<LandingIconKey, ComponentType<{ className?: string }>> = {
  workflow: Route,
  shield: ShieldCheck,
  globe: Globe2,
  api: Braces,
  factory: Route,
  scale: ShieldCheck,
  wrench: Braces,
  scan: Globe2,
};

const defaultTenant = (import.meta.env.VITE_DEFAULT_TENANT ?? 'default').trim().toLowerCase();

export default function LandingPage() {
  const auth = useAuth();

  return (
    <div className="landing-shell min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-landing-ink focus:shadow-md focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>

      <LandingHeader />

      <main id="main-content" className="pb-6">
        <HeroSection />
        <AudienceSegmentsSection />
        <LandingMetricsSection tenantSlug={defaultTenant || 'default'} />

        <AnimatedSection className="scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
          <section id="workflow" className="mx-auto max-w-6xl">
            <div className="grid gap-10 lg:grid-cols-[1fr_1fr] lg:items-start">
              <div>
                <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
                  Capability workflow narrative
                </p>
                <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
                  From modeling to publication, with guarded public visibility
                </h2>
                <ol className="mt-6 space-y-4">
                  {landingContent.capabilitySteps.map((step, index) => (
                    <li key={step.title} className="flex items-start gap-3">
                      <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-landing-cyan/35 bg-landing-cyan/10 text-xs font-semibold text-landing-cyan">
                        {index + 1}
                      </span>
                      <div>
                        <h3 className="font-display text-xl font-semibold text-landing-ink">{step.title}</h3>
                        <p className="mt-1 text-sm leading-relaxed text-landing-muted sm:text-base">
                          {step.description}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {landingContent.capabilityCards.map((card) => {
                  const Icon = capabilityIcons[card.icon] ?? Route;
                  return (
                    <article
                      key={card.title}
                      className="landing-panel rounded-2xl border border-landing-ink/12 bg-white/75 p-5 shadow-[0_24px_44px_-38px_rgba(15,38,51,0.76)]"
                    >
                      <span className="inline-flex rounded-full border border-landing-cyan/30 bg-landing-cyan/10 p-2 text-landing-cyan">
                        <Icon className="h-4 w-4" />
                      </span>
                      <h3 className="mt-4 font-display text-xl font-semibold text-landing-ink">{card.title}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-landing-muted">{card.body}</p>
                    </article>
                  );
                })}
              </div>
            </div>
          </section>
        </AnimatedSection>

        <AnimatedSection className="scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
          <section id="standards" className="mx-auto max-w-6xl">
            <div className="max-w-3xl">
              <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
                Standards and evidence links
              </p>
              <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
                Qualified claims with source references
              </h2>
              <p className="mt-4 text-base leading-relaxed text-landing-muted sm:text-lg">
                Regulatory and interoperability language is intentionally scoped. Every claim includes
                either a qualifier or an evidence link so audiences can validate context quickly.
              </p>
            </div>

            <div className="mt-8 grid gap-4 lg:grid-cols-3">
              {landingContent.standardsClaims.map((claim) => (
                <article
                  key={claim.title}
                  className="rounded-2xl border border-landing-ink/12 bg-white/78 p-5 shadow-[0_22px_42px_-36px_rgba(16,37,52,0.8)]"
                >
                  <h3 className="font-display text-2xl font-semibold leading-tight text-landing-ink">
                    {claim.title}
                  </h3>
                  <p className="mt-3 text-sm leading-relaxed text-landing-muted">{claim.qualifier}</p>
                  <ul className="mt-4 space-y-2">
                    {claim.evidence.map((evidence) => (
                      <li key={evidence.href}>
                        <a
                          href={evidence.href}
                          target={evidence.href.startsWith('http') ? '_blank' : undefined}
                          rel={evidence.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                          className="text-sm font-medium text-landing-cyan transition-colors hover:text-landing-ink"
                        >
                          {evidence.label}
                        </a>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </section>
        </AnimatedSection>

        <DataExposureSection />

        <AnimatedSection className="px-4 pb-16 pt-8 sm:px-6 lg:px-8">
          <section className="mx-auto max-w-6xl rounded-3xl border border-landing-cyan/25 bg-gradient-to-r from-landing-cyan/10 via-white to-landing-amber/10 p-8">
            <h2 className="font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
              Move from public trust to authenticated workflows
            </h2>
            <p className="mt-3 max-w-3xl text-base leading-relaxed text-landing-muted sm:text-lg">
              Use the secure sign-in path to create, review, and publish detailed passports while
              keeping first-page communication aggregate-only and policy-aligned.
            </p>
            <Button className="mt-6 rounded-full px-6" onClick={() => auth.signinRedirect()}>
              {landingContent.hero.primaryCta}
            </Button>
          </section>
        </AnimatedSection>
      </main>

      <LandingFooter />
    </div>
  );
}
