import { landingContent } from '../content/landingContent';

export default function HowItWorksSection() {
  return (
    <section id="workflow" className="landing-section-spacing scroll-mt-24 px-4 sm:px-6 lg:px-8">
      <div className="landing-container landing-panel-premium bg-gradient-to-r from-white/94 via-landing-surface-0/92 to-landing-surface-1/78 p-6 sm:p-8">
        <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
          How it works
        </p>
        <h2 className="landing-section-title mt-3 font-display text-landing-ink">
          Model, publish, and share trusted product data
        </h2>
        <p className="landing-lead mt-4 max-w-3xl text-landing-muted">
          The lifecycle is intentionally simple: build the passport structure, publish a verifiable record,
          and expose the right view to the right audience.
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {landingContent.howItWorksSteps.map((step, index) => (
            <article
              key={step.title}
              className="landing-card landing-hover-card rounded-[20px] border-landing-ink/12 bg-white/90 p-4"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                Step {index + 1}
              </p>
              <h3 className="mt-2 font-display text-2xl font-semibold text-landing-ink">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-landing-muted">{step.description}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
