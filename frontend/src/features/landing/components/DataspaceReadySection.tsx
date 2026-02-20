import ClaimLevelBadge from './ClaimLevelBadge';
import { landingContent } from '../content/landingContent';

export default function DataspaceReadySection() {
  return (
    <section className="landing-section-spacing px-4 sm:px-6 lg:px-8">
      <div className="landing-container">
        <div className="max-w-4xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            Dataspace-ready
          </p>
          <h2 className="landing-section-title mt-3 font-display text-landing-ink">
            Sovereign sharing language, grounded in implementation
          </h2>
          <p className="landing-lead mt-4 text-landing-muted">
            Connectors, resolver pathways, and policy controls are positioned with evidence-first
            claim discipline for technical due diligence.
          </p>
        </div>

        <div className="mt-7 grid gap-4 md:grid-cols-3">
          {landingContent.dataspaceCards.map((card) => (
            <article
              key={card.title}
              className="landing-card landing-hover-card rounded-[20px] border-landing-ink/12 bg-landing-surface-0/84 p-5"
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
                className="landing-cta mt-4 inline-flex text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
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
