import { ArrowUpRight, FileJson2, GitBranch, Link2 } from 'lucide-react';
import { landingContent } from '../content/landingContent';

export default function SamplePassportSection() {
  return (
    <section id="sample-passport" className="scroll-mt-24 px-4 pb-14 sm:px-6 sm:pb-16 lg:px-8">
      <div className="mx-auto max-w-6xl rounded-3xl border border-landing-ink/12 bg-white/85 p-6 shadow-[0_24px_52px_-38px_rgba(9,35,46,0.68)] sm:p-8">
        <div className="grid gap-8 lg:grid-cols-[1fr_1fr] lg:items-start">
          <div>
            <p className="landing-kicker text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">
              Sample Passport
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-landing-ink sm:text-4xl">
              {landingContent.samplePassport.title}
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-landing-muted sm:text-lg">
              {landingContent.samplePassport.description}
            </p>

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

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <a
                className="inline-flex items-center gap-1.5 rounded-full border border-landing-cyan/35 bg-landing-cyan/10 px-4 py-2 text-sm font-semibold text-landing-cyan transition-colors hover:border-landing-cyan/60 hover:bg-landing-cyan/15"
                href="/api/v1/docs"
              >
                <Link2 className="h-4 w-4" />
                Inspect API surface
              </a>
              <a
                className="inline-flex items-center gap-1.5 rounded-full border border-landing-ink/20 bg-white px-4 py-2 text-sm font-semibold text-landing-ink transition-colors hover:border-landing-ink/35"
                href="https://github.com/hadijannat/mini-dpp-platform#quick-start-docker-compose"
                target="_blank"
                rel="noopener noreferrer"
              >
                <ArrowUpRight className="h-4 w-4" />
                Quickstart commands
              </a>
            </div>
          </div>

          <div className="relative overflow-hidden rounded-2xl border border-landing-ink/12 bg-[hsl(var(--landing-ink))] p-5 text-emerald-100">
            <div className="mb-4 flex items-center justify-between">
              <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-300/90">
                <FileJson2 className="h-4 w-4" />
                AAS Snapshot
              </p>
              <span className="inline-flex items-center gap-1 text-xs text-emerald-300/80">
                <GitBranch className="h-3.5 w-3.5" />
                public-safe preview
              </span>
            </div>
            <pre className="overflow-x-auto rounded-xl border border-emerald-400/20 bg-black/20 p-4 text-[12px] leading-relaxed text-emerald-100">
              <code>{landingContent.samplePassport.aasSnippet}</code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
