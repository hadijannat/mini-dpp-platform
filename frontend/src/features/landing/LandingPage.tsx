import { lazy, Suspense } from 'react';
import { Button } from '@/components/ui/button';
import DeferredSection from './components/DeferredSection';
import DataExposureSection from './components/DataExposureSection';
import FAQSection from './components/FAQSection';
import HeroSection from './components/HeroSection';
import HowItWorksSection from './components/HowItWorksSection';
import CirpassLabTeaserSection from './components/CirpassLabTeaserSection';
import LandingFooter from './components/LandingFooter';
import LandingHeader from './components/LandingHeader';
import LandingMetricsSection from './components/LandingMetricsSection';
import LandingSectionMotion from './components/LandingSectionMotion';
import RegulatoryTimelineSection from './components/RegulatoryTimelineSection';
import SamplePassportSection from './components/SamplePassportSection';
import { landingContent } from './content/landingContent';

const StandardsMapSection = lazy(() => import('./components/StandardsMapSection'));
const DataspaceReadySection = lazy(() => import('./components/DataspaceReadySection'));
const DeveloperTrustSection = lazy(() => import('./components/DeveloperTrustSection'));

export default function LandingPage() {
  const faqJsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: landingContent.faq.map((entry) => ({
      '@type': 'Question',
      name: entry.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: entry.answer,
      },
    })),
  });

  return (
    <div className="landing-shell min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-landing-ink focus:shadow-md focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>

      <LandingHeader />

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: faqJsonLd }} />

      <main id="main-content" className="pb-6">
        <HeroSection />
        <LandingSectionMotion>
          <RegulatoryTimelineSection />
        </LandingSectionMotion>
        <LandingSectionMotion>
          <HowItWorksSection />
        </LandingSectionMotion>
        <LandingSectionMotion>
          <SamplePassportSection />
        </LandingSectionMotion>
        <LandingSectionMotion>
          <CirpassLabTeaserSection />
        </LandingSectionMotion>

        <DeferredSection minHeight={360} sectionId="metrics">
          <LandingSectionMotion>
            <LandingMetricsSection scope="all" />
          </LandingSectionMotion>
        </DeferredSection>

        <DeferredSection minHeight={420} sectionId="standards">
          <Suspense fallback={<div className="h-[420px]" aria-hidden="true" />}>
            <LandingSectionMotion>
              <StandardsMapSection />
            </LandingSectionMotion>
          </Suspense>
        </DeferredSection>

        <DeferredSection minHeight={320} sectionId="dataspaces">
          <Suspense fallback={<div className="h-[320px]" aria-hidden="true" />}>
            <LandingSectionMotion>
              <DataspaceReadySection />
            </LandingSectionMotion>
          </Suspense>
        </DeferredSection>

        <DeferredSection minHeight={320} sectionId="developers">
          <Suspense fallback={<div className="h-[320px]" aria-hidden="true" />}>
            <LandingSectionMotion>
              <DeveloperTrustSection />
            </LandingSectionMotion>
          </Suspense>
        </DeferredSection>

        <LandingSectionMotion>
          <FAQSection />
        </LandingSectionMotion>

        <LandingSectionMotion>
          <DataExposureSection />
        </LandingSectionMotion>

        <LandingSectionMotion>
          <section className="px-4 pb-16 pt-8 sm:px-6 lg:px-8">
            <div className="landing-container landing-panel-premium p-8 sm:p-10">
              <p className="landing-kicker text-xs font-semibold uppercase text-landing-muted">
                Ready to launch
              </p>
              <h2 className="landing-section-title mt-4 font-display text-landing-ink">
                {landingContent.finalCta.title}
              </h2>
              <p className="landing-lead mt-4 max-w-3xl text-landing-muted">{landingContent.finalCta.subtitle}</p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Button className="landing-cta h-12 rounded-full px-7 text-sm font-semibold" asChild>
                  <a href={landingContent.finalCta.primaryCtaHref}>{landingContent.finalCta.primaryCta}</a>
                </Button>
                <Button
                  variant="outline"
                  className="landing-cta h-12 rounded-full border-landing-ink/25 bg-white/75 px-7 text-sm font-semibold text-landing-ink"
                  asChild
                >
                  <a
                    href={landingContent.finalCta.secondaryCtaHref}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {landingContent.finalCta.secondaryCta}
                  </a>
                </Button>
              </div>
            </div>
          </section>
        </LandingSectionMotion>
      </main>

      <LandingFooter />
    </div>
  );
}
