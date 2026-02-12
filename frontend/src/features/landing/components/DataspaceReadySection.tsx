import ClaimLevelBadge from './ClaimLevelBadge';
import { landingContent } from '../content/landingContent';

export default function DataspaceReadySection() {
  return (
    <section id="dataspaces" className="scroll-mt-24 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="max-w-4xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            Dataspace-ready
          </p>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
            Sovereign sharing language, grounded in implementation
          </h2>
          <p className="mt-4 text-base leading-relaxed text-landing-muted sm:text-lg">
            Connectors, resolver pathways, and policy controls are positioned with evidence-first
            claim discipline for technical due diligence.
          </p>
        </div>

        <div className="mt-7 grid gap-4 md:grid-cols-3">
          {landingContent.dataspaceCards.map((card) => (
            <article
              key={card.title}
              className="rounded-2xl border border-landing-ink/12 bg-white/78 p-5 shadow-[0_20px_40px_-34px_rgba(16,35,50,0.72)]"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-display text-xl font-semibold text-landing-ink">{card.title}</h3>
                <ClaimLevelBadge level={card.claimLevel} />
              </div>
              <p className="mt-3 text-sm leading-relaxed text-landing-muted">{card.body}</p>
              <a
                href={card.evidence.href}
                target={card.evidence.href.startsWith('http') ? '_blank' : undefined}
                rel={card.evidence.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                className="mt-4 inline-flex text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
              >
                {card.evidence.label}
              </a>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
