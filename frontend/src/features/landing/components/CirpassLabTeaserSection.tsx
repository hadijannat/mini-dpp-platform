import { ArrowRight, Recycle, ShieldCheck, Wrench } from 'lucide-react';
import { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { useCirpassStories } from '@/features/cirpass-lab/hooks/useCirpassStories';
import { loadGeneratedCirpassManifest } from '@/features/cirpass-lab/schema/manifestLoader';

const roleCards = [
  {
    title: 'Manufacturer / REO',
    description: 'Start from CREATE and mint a compliant payload.',
    icon: ShieldCheck,
    href: '/cirpass-lab/story/core-loop-v3_1/step/create-passport?mode=mock&variant=happy',
  },
  {
    title: 'Consumer / Authority',
    description: 'Jump to ACCESS routing and role-policy checks.',
    icon: Wrench,
    href: '/cirpass-lab/story/core-loop-v3_1/step/access-routing?mode=mock&variant=happy',
  },
  {
    title: 'Repairer / Recycler',
    description: 'Explore UPDATE to DEACTIVATE circular flow.',
    icon: Recycle,
    href: '/cirpass-lab/story/core-loop-v3_1/step/update-repair-chain?mode=mock&variant=happy',
  },
] as const;

export default function CirpassLabTeaserSection() {
  const generatedManifest = useMemo(() => loadGeneratedCirpassManifest(), []);
  const storiesQuery = useCirpassStories();
  const defaultStory = generatedManifest.stories[0];
  const version = storiesQuery.data?.version ?? generatedManifest.story_version ?? 'V3.1';
  const learningGoals = defaultStory?.learning_goals.slice(0, 2) ?? [];
  const sourceRecord =
    storiesQuery.data?.zenodo_record_url ??
    defaultStory?.references.find((entry) => entry.ref.includes('zenodo'))?.ref ??
    'https://zenodo.org/records/17979585';

  const prefetchLab = () => {
    void import('@/features/cirpass-lab/pages/CirpassLabPage');
  };

  return (
    <section id="cirpass-lab" className="scroll-mt-24 px-4 py-14 sm:px-6 sm:py-16 lg:px-8">
      <div className="mx-auto max-w-6xl overflow-hidden rounded-3xl border border-landing-ink/15 bg-[linear-gradient(135deg,rgba(7,47,60,0.94),rgba(17,24,39,0.95))] p-6 text-white shadow-[0_32px_70px_-46px_rgba(7,47,60,0.88)] sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-cyan-200/35 bg-cyan-200/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.13em] text-cyan-100">
              <ShieldCheck className="h-3.5 w-3.5" />
              Public Learn-by-Doing Lab
            </p>
            <h2 className="mt-4 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              LoopForge: CIRPASS Twin-Layer Lab
            </h2>
            <p className="mt-3 max-w-3xl text-base leading-relaxed text-slate-100 sm:text-lg">
              Build the lifecycle step-by-step and inspect API, artifact, and policy behavior while
              you play.
            </p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-[0.11em] text-slate-200">
              <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">
                Latest release: {version}
              </span>
              <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">
                Issue, access, update, exchange, modify
              </span>
              {learningGoals.map((goal) => (
                <span key={goal} className="rounded-full border border-white/20 bg-white/10 px-3 py-1 normal-case tracking-normal">
                  {goal}
                </span>
              ))}
              <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">
                Mock mode default
              </span>
            </div>
          </div>

          <div className="rounded-2xl border border-white/15 bg-white/8 p-4">
            <p className="text-sm leading-relaxed text-slate-100">
              Mission formula: score = 1000 - (errors × 25) - (hints × 40) - floor(time/3) +
              (perfect levels × 60).
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                asChild
                className="rounded-full px-6"
                data-testid="cirpass-teaser-primary"
                onMouseEnter={prefetchLab}
                onFocus={prefetchLab}
              >
                <a href="/cirpass-lab">
                  Open CIRPASS Lab
                  <ArrowRight className="h-4 w-4" />
                </a>
              </Button>
              <Button
                variant="outline"
                className="rounded-full border-white/25 bg-white/10 px-6 text-white hover:bg-white/20"
                asChild
              >
                <a
                  href={sourceRecord}
                  target="_blank"
                  rel="noopener noreferrer"
                >
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

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {roleCards.map((card) => (
            <a
              key={card.title}
              href={card.href}
              className="group rounded-2xl border border-white/20 bg-white/10 p-4 transition hover:bg-white/15"
              onMouseEnter={prefetchLab}
              onFocus={prefetchLab}
            >
              <card.icon className="h-5 w-5 text-cyan-100" aria-hidden="true" />
              <p className="mt-2 text-sm font-semibold text-white">{card.title}</p>
              <p className="mt-1 text-sm text-slate-200">{card.description}</p>
              <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.11em] text-cyan-100">
                Start role path
                <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
              </span>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
