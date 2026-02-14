import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import type { CirpassLevel } from '@/api/types';
import StoryRunner from '../components/StoryRunner';
import { useCirpassSession } from '../hooks/useCirpassSession';
import { useCirpassStories } from '../hooks/useCirpassStories';

const fallbackLevels: CirpassLevel[] = [
  {
    level: 'create',
    label: 'CREATE',
    objective: 'Build a complete DPP payload with mandatory sustainability fields.',
    stories: [
      {
        id: 'create-fallback',
        title: 'Initialize a compliant passport',
        summary: 'Responsible operators compose required DPP attributes before market entry.',
      },
    ],
  },
  {
    level: 'access',
    label: 'ACCESS',
    objective: 'Route role-based views so each actor receives only permitted information.',
    stories: [
      {
        id: 'access-fallback',
        title: 'Control role visibility',
        summary: 'Consumers and authorities receive different views under policy constraints.',
      },
    ],
  },
  {
    level: 'update',
    label: 'UPDATE',
    objective: 'Append trusted lifecycle updates without breaking provenance links.',
    stories: [
      {
        id: 'update-fallback',
        title: 'Record trusted repair event',
        summary: 'Repair actions append to lifecycle history while keeping chain integrity.',
      },
    ],
  },
  {
    level: 'transfer',
    label: 'TRANSFER',
    objective: 'Transfer custody and ownership while preserving confidentiality boundaries.',
    stories: [
      {
        id: 'transfer-fallback',
        title: 'Secure handover',
        summary: 'Ownership moves across actors while sensitive fields remain restricted.',
      },
    ],
  },
  {
    level: 'deactivate',
    label: 'DEACTIVATE',
    objective: 'Close lifecycle and surface material recovery insights for circularity.',
    stories: [
      {
        id: 'deactivate-fallback',
        title: 'Close and loop',
        summary: 'End-of-life state enables next-life material intelligence.',
      },
    ],
  },
];

export default function CirpassLabPage() {
  const storiesQuery = useCirpassStories();
  const sessionQuery = useCirpassSession();

  const version = storiesQuery.data?.version ?? 'V3.1';
  const levels = storiesQuery.data?.levels ?? fallbackLevels;

  return (
    <div className="px-4 pb-16 pt-10 sm:px-6 lg:px-8" data-testid="cirpass-lab-page">
      <div className="mx-auto max-w-7xl">
        <div className="mb-4">
          <Button
            asChild
            variant="ghost"
            className="rounded-full border border-landing-cyan/35 bg-white/85 text-landing-ink hover:bg-white"
          >
            <Link to="/" data-testid="cirpass-back-home">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to homepage
            </Link>
          </Button>
        </div>

        <div className="rounded-3xl border border-landing-cyan/25 bg-gradient-to-r from-landing-cyan/10 via-white to-landing-amber/10 p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-landing-muted">LoopForge</p>
          <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-landing-ink sm:text-5xl">
            CIRPASS Twin-Layer Simulator
          </h1>
          <p className="mt-3 max-w-4xl text-base leading-relaxed text-landing-muted sm:text-lg">
            Play through CREATE, ACCESS, UPDATE, TRANSFER, and DEACTIVATE while toggling between
            physical and technical dimensions.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <span className="rounded-full border border-landing-ink/12 bg-white px-3 py-1 font-semibold text-landing-ink">
              Version {version}
            </span>
            <span className="rounded-full border border-landing-ink/12 bg-white px-3 py-1 text-landing-muted">
              Source: official CIRPASS + Zenodo
            </span>
            {storiesQuery.data?.source_status === 'stale' && (
              <span className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1 font-semibold text-amber-700" data-testid="cirpass-source-stale">
                Source stale · refreshing in background
              </span>
            )}
          </div>
        </div>

        <StoryRunner
          version={version}
          levels={levels}
          sourceStatus={storiesQuery.data?.source_status}
          storiesLoading={storiesQuery.isLoading}
          storiesError={storiesQuery.isError}
          sessionToken={sessionQuery.data?.session_token ?? null}
        />
      </div>
    </div>
  );
}
