import { landingContent } from '../content/landingContent';

export default function HowItWorksSection() {
  return (
    <section id="workflow" className="scroll-mt-24 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl rounded-3xl border border-landing-ink/12 bg-white/78 p-6 shadow-[0_24px_48px_-36px_rgba(12,36,49,0.75)] sm:p-8">
        <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
          How it works
        </p>
        <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
          Model, publish, share
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {landingContent.howItWorksSteps.map((step, index) => (
            <article key={step.title} className="rounded-2xl border border-landing-ink/10 bg-landing-surface-0/75 p-4">
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
