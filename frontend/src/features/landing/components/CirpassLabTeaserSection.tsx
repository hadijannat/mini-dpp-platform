import { ArrowRight, Rocket } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useCirpassStories } from '@/features/cirpass-lab/hooks/useCirpassStories';

export default function CirpassLabTeaserSection() {
  const storiesQuery = useCirpassStories();
  const version = storiesQuery.data?.version ?? 'V3.1';

  return (
    <section id="cirpass-lab" className="scroll-mt-24 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl overflow-hidden rounded-3xl border border-landing-ink/15 bg-[linear-gradient(135deg,rgba(7,47,60,0.94),rgba(17,24,39,0.95))] p-6 text-white shadow-[0_32px_70px_-46px_rgba(7,47,60,0.88)] sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan-200/35 bg-cyan-200/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.13em] text-cyan-100">
              <Rocket className="h-3.5 w-3.5" />
              New Public Experience
            </p>
            <h2 className="mt-4 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              LoopForge: CIRPASS Twin-Layer Lab
            </h2>
            <p className="mt-3 max-w-3xl text-base leading-relaxed text-slate-100 sm:text-lg">
              Explore the latest CIRPASS user stories with a gamified simulator that flips between
              joyful product-world interactions and technical process logic.
            </p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.11em] text-slate-200">
              <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">
                Latest release: {version}
              </span>
              <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">
                5 lifecycle levels
              </span>
              <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">
                Spacebar twin-layer flip
              </span>
            </div>
          </div>

          <div className="rounded-2xl border border-white/15 bg-white/8 p-4">
            <p className="text-sm leading-relaxed text-slate-100">
              Mission formula: score = 1000 - (errors × 25) - (hints × 40) - floor(time/3) +
              (perfect levels × 60).
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button asChild className="rounded-full px-6" data-testid="cirpass-teaser-primary">
                <a href="/cirpass-lab">
                  Open CIRPASS Lab
                  <ArrowRight className="h-4 w-4" />
                </a>
              </Button>
              <Button variant="outline" className="rounded-full border-white/25 bg-white/10 px-6 text-white hover:bg-white/20" asChild>
                <a href={storiesQuery.data?.zenodo_record_url ?? 'https://zenodo.org/records/17979585'} target="_blank" rel="noopener noreferrer">
                  Source record
                </a>
              </Button>
            </div>
            {storiesQuery.data?.source_status === 'stale' && (
              <p className="mt-3 text-xs font-semibold uppercase tracking-[0.1em] text-amber-200" data-testid="cirpass-teaser-stale">
                Source sync in progress
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
