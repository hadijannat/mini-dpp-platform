import LandingHeader from './components/LandingHeader';
import HeroSection from './components/HeroSection';
import WhatIsDPPSection from './components/WhatIsDPPSection';
import StandardsSection from './components/StandardsSection';
import CircularEconomySection from './components/CircularEconomySection';
import PlatformFeaturesSection from './components/PlatformFeaturesSection';
import LandingFooter from './components/LandingFooter';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Skip to content link for keyboard users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow-md focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>

      <LandingHeader />

      <main id="main-content">
        <HeroSection />
        <WhatIsDPPSection />
        <StandardsSection />
        <CircularEconomySection />
        <PlatformFeaturesSection />
      </main>

      <LandingFooter />
    </div>
  );
}
