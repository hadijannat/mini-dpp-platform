import { Button } from '@/components/ui/button';
import EvidenceGovernanceSection from './components/EvidenceGovernanceSection';
import HeroSection from './components/HeroSection';
import LandingFooter from './components/LandingFooter';
import LandingHeader from './components/LandingHeader';
import ProofStripSection from './components/ProofStripSection';
import SamplePassportSection from './components/SamplePassportSection';
import { landingContent } from './content/landingContent';

export default function LandingPage() {
  const faqJsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: landingContent.faq.slice(0, 3).map((entry) => ({
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

      <main id="main-content" className="pb-8">
        <div className="landing-reveal landing-reveal-1">
          <HeroSection />
        </div>
        <div className="landing-reveal landing-reveal-2">
          <ProofStripSection />
        </div>
        <div className="landing-reveal landing-reveal-3">
          <SamplePassportSection />
        </div>
        <div className="landing-reveal landing-reveal-4">
          <EvidenceGovernanceSection />
        </div>

        <section id="launch" className="landing-reveal landing-reveal-5 px-4 pb-16 pt-8 sm:px-6 lg:px-8">
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
