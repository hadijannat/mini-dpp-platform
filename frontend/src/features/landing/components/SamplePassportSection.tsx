import { ArrowUpRight, FileJson2, GitBranch, Link2, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { landingContent } from '../content/landingContent';

export default function SamplePassportSection() {
  return (
    <section id="sample-passport" className="scroll-mt-24 px-4 pb-14 sm:px-6 sm:pb-16 lg:px-8">
      <div className="mx-auto max-w-6xl rounded-3xl border border-landing-ink/12 bg-white/86 p-6 shadow-[0_24px_52px_-38px_rgba(9,35,46,0.7)] sm:p-8">
        <div className="grid gap-8 lg:grid-cols-[1fr_1fr] lg:items-start">
          <div>
            <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
              Demo passport flow
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
              {landingContent.samplePassport.title}
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-landing-muted sm:text-lg">
              {landingContent.samplePassport.description}
            </p>

            <div className="mt-5 rounded-2xl border border-landing-cyan/24 bg-gradient-to-r from-landing-cyan/10 to-landing-amber/10 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.1em] text-landing-muted">
                Viewer URL shape
              </p>
              <code className="mt-2 block rounded-lg bg-white/80 px-3 py-2 font-mono text-xs text-landing-ink sm:text-sm">
                {landingContent.samplePassport.viewerPathHint}
              </code>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button asChild className="rounded-full px-6 text-sm font-semibold">
                  <a href={landingContent.samplePassport.demoCtaHref}>
                    {landingContent.samplePassport.demoCtaLabel}
                    <ArrowUpRight className="h-4 w-4" />
                  </a>
                </Button>
                <Button
                  variant="outline"
                  asChild
                  className="rounded-full border-landing-ink/24 bg-white px-5 text-sm font-semibold text-landing-ink"
                >
                  <a href="/api/v1/docs">
                    <Link2 className="h-4 w-4" />
                    Inspect API surface
                  </a>
                </Button>
              </div>
            </div>

            <div className="mt-5 grid gap-3 text-sm leading-relaxed text-landing-muted">
              <p className="rounded-xl border border-landing-ink/10 bg-landing-surface-0/70 p-3">
                <span className="font-semibold text-landing-ink">Why this matters (business): </span>
                {landingContent.samplePassport.businessValue}
              </p>
              <p className="rounded-xl border border-landing-ink/10 bg-landing-surface-0/70 p-3">
                <span className="font-semibold text-landing-ink">Verify quickly (engineering): </span>
                {landingContent.samplePassport.technicalValue}
              </p>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {landingContent.samplePassport.nodes.map((node) => (
                <article
                  key={node.label}
                  className="rounded-2xl border border-landing-ink/10 bg-landing-surface-0/80 px-4 py-3"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-landing-muted">
                    {node.label}
                  </p>
                  <p className="mt-1 break-all font-mono text-xs text-landing-ink sm:text-sm">{node.value}</p>
                </article>
              ))}
            </div>
          </div>

          <div className="relative overflow-hidden rounded-2xl border border-landing-ink/12 bg-[hsl(var(--landing-ink))] p-5 text-emerald-100">
            <div className="mb-4 flex items-center justify-between">
              <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-300/90">
                <FileJson2 className="h-4 w-4" />
                AAS snapshot
              </p>
              <span className="inline-flex items-center gap-1 text-xs text-emerald-300/80">
                <GitBranch className="h-3.5 w-3.5" />
                public-safe preview
              </span>
            </div>
            <pre className="overflow-x-auto rounded-xl border border-emerald-400/20 bg-black/20 p-4 text-[12px] leading-relaxed text-emerald-100">
              <code>{landingContent.samplePassport.aasSnippet}</code>
            </pre>
            <p className="mt-3 inline-flex items-center gap-2 text-xs text-emerald-200/85">
              <Sparkles className="h-3.5 w-3.5" />
              Keep this snippet compact on landing; detailed payloads stay in protected views.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
