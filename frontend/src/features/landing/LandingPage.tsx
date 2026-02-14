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
        <HowItWorksSection />
        <CirpassLabTeaserSection />
        <SamplePassportSection />

        <DeferredSection minHeight={360} sectionId="metrics">
          <LandingMetricsSection scope="all" />
        </DeferredSection>

        <DeferredSection minHeight={420} sectionId="standards">
          <Suspense fallback={<div className="h-[420px]" aria-hidden="true" />}>
            <StandardsMapSection />
          </Suspense>
        </DeferredSection>

        <DeferredSection minHeight={320} sectionId="dataspaces">
          <Suspense fallback={<div className="h-[320px]" aria-hidden="true" />}>
            <DataspaceReadySection />
          </Suspense>
        </DeferredSection>

        <DeferredSection minHeight={320} sectionId="developers">
          <Suspense fallback={<div className="h-[320px]" aria-hidden="true" />}>
            <DeveloperTrustSection />
          </Suspense>
        </DeferredSection>

        <FAQSection />

        <DataExposureSection />

        <section className="px-4 pb-16 pt-8 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-6xl rounded-3xl border border-landing-cyan/25 bg-gradient-to-r from-landing-cyan/10 via-white to-landing-amber/10 p-8">
            <h2 className="font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
              {landingContent.finalCta.title}
            </h2>
            <p className="mt-3 max-w-3xl text-base leading-relaxed text-landing-muted sm:text-lg">
              {landingContent.finalCta.subtitle}
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Button className="rounded-full px-6" asChild>
                <a href={landingContent.finalCta.primaryCtaHref}>{landingContent.finalCta.primaryCta}</a>
              </Button>
              <Button variant="outline" className="rounded-full px-6" asChild>
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
      </main>

      <LandingFooter />
    </div>
  );
}
