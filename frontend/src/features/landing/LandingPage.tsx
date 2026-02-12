import { lazy, Suspense } from 'react';
import { useAuth } from 'react-oidc-context';
import { Button } from '@/components/ui/button';
import AudienceSegmentsSection from './components/AudienceSegmentsSection';
import DeferredSection from './components/DeferredSection';
import DataExposureSection from './components/DataExposureSection';
import HeroSection from './components/HeroSection';
import HowItWorksSection from './components/HowItWorksSection';
import LandingFooter from './components/LandingFooter';
import LandingHeader from './components/LandingHeader';
import LandingMetricsSection from './components/LandingMetricsSection';
import SamplePassportSection from './components/SamplePassportSection';

const StandardsMapSection = lazy(() => import('./components/StandardsMapSection'));
const DataspaceReadySection = lazy(() => import('./components/DataspaceReadySection'));
const DeveloperTrustSection = lazy(() => import('./components/DeveloperTrustSection'));

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
        <SamplePassportSection />
        <AudienceSegmentsSection />

        <DeferredSection minHeight={420}>
          <Suspense fallback={<div className="h-[420px]" aria-hidden="true" />}>
            <StandardsMapSection />
          </Suspense>
        </DeferredSection>

        <DeferredSection minHeight={320}>
          <Suspense fallback={<div className="h-[320px]" aria-hidden="true" />}>
            <DataspaceReadySection />
          </Suspense>
        </DeferredSection>

        <HowItWorksSection />

        <DeferredSection minHeight={320}>
          <Suspense fallback={<div className="h-[320px]" aria-hidden="true" />}>
            <DeveloperTrustSection />
          </Suspense>
        </DeferredSection>

        <DeferredSection minHeight={360}>
          <LandingMetricsSection scope="all" />
        </DeferredSection>

        <DataExposureSection />

        <section className="px-4 pb-16 pt-8 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-6xl rounded-3xl border border-landing-cyan/25 bg-gradient-to-r from-landing-cyan/10 via-white to-landing-amber/10 p-8">
            <h2 className="font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
              Move from public trust to authenticated workflows
            </h2>
            <p className="mt-3 max-w-3xl text-base leading-relaxed text-landing-muted sm:text-lg">
              Use secure sign-in to create, review, and publish detailed passports while keeping
              first-screen communication aggregate-only and evidence-linked.
            </p>
            <Button className="mt-6 rounded-full px-6" onClick={() => auth.signinRedirect()}>
              Open publisher or admin console
            </Button>
          </div>
        </section>
      </main>

      <LandingFooter />
    </div>
  );
}
