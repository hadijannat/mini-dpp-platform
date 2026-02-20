import ClaimLevelBadge from './ClaimLevelBadge';
import { landingContent } from '../content/landingContent';

export default function StandardsMapSection() {
  return (
    <section className="landing-section-spacing bg-landing-surface-1/42 px-4 sm:px-6 lg:px-8">
      <div className="landing-container">
        <div className="max-w-4xl">
          <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
            Standards map
          </p>
          <h2 className="landing-section-title mt-3 font-display text-landing-ink">
            Capability claims with explicit evidence
          </h2>
          <p className="landing-lead mt-4 text-landing-muted">
            Claims are intentionally conservative and tagged as Implements, Aligned, or Roadmap so
            technical reviewers can verify scope quickly.
          </p>
        </div>

        <div className="mt-7 grid gap-4 lg:grid-cols-2">
          {landingContent.standardsMap.map((row) => (
            <article
              key={row.title}
              className="landing-card landing-hover-card rounded-[20px] border-landing-ink/12 bg-white/84 p-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-display text-xl font-semibold text-landing-ink">{row.title}</h3>
                <ClaimLevelBadge level={row.claimLevel} />
              </div>
              <p className="mt-3 text-sm leading-relaxed text-landing-muted">{row.outcome}</p>
              <p className="mt-2 text-sm leading-relaxed text-landing-muted">{row.qualifier}</p>
              <a
                href={row.evidence.href}
                target={row.evidence.href.startsWith('http') ? '_blank' : undefined}
                rel={row.evidence.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                className="landing-cta mt-4 inline-flex text-sm font-semibold text-landing-cyan transition-colors hover:text-landing-ink"
              >
                {row.evidence.label}
              </a>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
