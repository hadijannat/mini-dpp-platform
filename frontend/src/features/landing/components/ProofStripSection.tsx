import { LockKeyhole, ShieldCheck } from 'lucide-react';
import LandingMetricsSection from './LandingMetricsSection';
import { landingContent } from '../content/landingContent';

export default function ProofStripSection() {
  return (
    <section id="proof-strip" className="scroll-mt-24 px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
      <div className="mx-auto max-w-6xl rounded-3xl border border-landing-cyan/20 bg-white/85 p-6 shadow-[0_24px_44px_-34px_rgba(9,32,45,0.76)] sm:p-8">
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
          <div>
            <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
              {landingContent.proofStrip.eyebrow}
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
              {landingContent.proofStrip.title}
            </h2>
            <p className="mt-3 max-w-3xl text-base leading-relaxed text-landing-muted sm:text-lg">
              {landingContent.proofStrip.subtitle}
            </p>

            <div className="mt-4 flex flex-wrap gap-2" data-testid="proof-strip-badges">
              {landingContent.proofStrip.badges.map((badge) => (
                <span
                  key={badge}
                  className="inline-flex rounded-full border border-landing-ink/14 bg-landing-surface-0/75 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] text-landing-ink"
                >
                  {badge}
                </span>
              ))}
            </div>

            <div className="mt-6 grid gap-3 text-sm leading-relaxed text-landing-muted sm:grid-cols-2">
              {landingContent.proofStrip.trustClaims.map((claim) => (
                <div key={claim} className="flex items-start gap-2.5 rounded-xl border border-landing-ink/10 bg-white/70 p-3">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-landing-cyan" />
                  <span>{claim}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-landing-ink/12 bg-landing-surface-0/65 p-4 sm:p-5">
            <LandingMetricsSection scope="all" variant="compact" />
            <div className="mt-4 rounded-xl border border-landing-ink/12 bg-white/70 p-3.5">
              <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.1em] text-landing-muted">
                <LockKeyhole className="h-3.5 w-3.5 text-landing-cyan" />
                Privacy boundary
              </p>
              <p className="mt-2 text-sm leading-relaxed text-landing-muted">
                {landingContent.proofStrip.privacySummary}
              </p>
              <a
                href={landingContent.proofStrip.privacyLink.href}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
                data-testid="proof-strip-privacy-link"
              >
                {landingContent.proofStrip.privacyLink.label}
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
