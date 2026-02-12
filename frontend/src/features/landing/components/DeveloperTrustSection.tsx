import { Braces, ShieldCheck, UserCog, Wrench } from 'lucide-react';
import { landingContent } from '../content/landingContent';

const signalIcons = [Braces, UserCog, Wrench, ShieldCheck] as const;

const endpointLinks = [
  { label: 'API docs', href: '/api/v1/docs' },
  { label: 'OpenAPI', href: '/api/v1/openapi.json' },
  {
    label: 'Quickstart',
    href: 'https://github.com/hadijannat/mini-dpp-platform#quick-start-docker-compose',
  },
] as const;

export default function DeveloperTrustSection() {
  return (
    <section id="developers" className="scroll-mt-24 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="max-w-4xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            Developer trust strip
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
            Run today, verify quickly
          </h2>
          <p className="mt-4 text-base leading-relaxed text-landing-muted sm:text-lg">
            API contract clarity, policy and IAM controls, and local reproducibility are surfaced
            directly in the first public experience.
          </p>
        </div>

        <div className="mt-7 grid gap-4 md:grid-cols-2">
          {landingContent.developerSignals.map((signal, index) => {
            const Icon = signalIcons[index % signalIcons.length];
            return (
              <article
                key={signal.title}
                className="rounded-2xl border border-landing-ink/12 bg-white/78 p-5 shadow-[0_20px_40px_-34px_rgba(16,35,50,0.72)]"
              >
                <p className="inline-flex rounded-full border border-landing-cyan/30 bg-landing-cyan/10 p-2 text-landing-cyan">
                  <Icon className="h-4 w-4" />
                </p>
                <h3 className="mt-3 font-display text-xl font-semibold text-landing-ink">{signal.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-landing-muted">{signal.detail}</p>
              </article>
            );
          })}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {endpointLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              target={link.href.startsWith('http') ? '_blank' : undefined}
              rel={link.href.startsWith('http') ? 'noopener noreferrer' : undefined}
              className="inline-flex rounded-full border border-landing-ink/18 bg-white px-4 py-2 text-sm font-semibold text-landing-ink transition-colors hover:border-landing-cyan/40 hover:text-landing-cyan"
            >
              {link.label}
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
