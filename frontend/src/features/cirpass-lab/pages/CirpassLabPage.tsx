import { useEffect, useMemo, useRef, useState } from 'react';
import { useMachine } from '@xstate/react';
import * as htmlToImage from 'html-to-image';
import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import type { CirpassLevel } from '@/api/types';
import type {
  AccessLevelPayload,
  CreateLevelPayload,
  DeactivateLevelPayload,
  TransferLevelPayload,
  UpdateLevelPayload,
} from '../machines/cirpassMachine';
import { cirpassMachine, type CirpassLevelKey } from '../machines/cirpassMachine';
import { computeLoopForgeScore } from '../utils/scoring';
import { useCirpassLeaderboard } from '../hooks/useCirpassLeaderboard';
import { useCirpassSession } from '../hooks/useCirpassSession';
import { useCirpassStories } from '../hooks/useCirpassStories';
import JoyfulLayer from '../components/JoyfulLayer';
import LeaderboardPanel from '../components/LeaderboardPanel';
import MissionPanel from '../components/MissionPanel';
import ScoreHud from '../components/ScoreHud';
import TechnicalLayer from '../components/TechnicalLayer';
import TwinLayerShell from '../components/TwinLayerShell';

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

const levelLabels: Record<CirpassLevelKey, string> = {
  create: 'Level 1 · CREATE',
  access: 'Level 2 · ACCESS',
  update: 'Level 3 · UPDATE',
  transfer: 'Level 4 · TRANSFER',
  deactivate: 'Level 5 · DEACTIVATE',
};

function resolveCurrentLevel(rawValue: unknown): CirpassLevelKey | 'completed' {
  if (rawValue === 'create') return 'create';
  if (rawValue === 'access') return 'access';
  if (rawValue === 'update') return 'update';
  if (rawValue === 'transfer') return 'transfer';
  if (rawValue === 'deactivate') return 'deactivate';
  return 'completed';
}

type PayloadShape =
  | CreateLevelPayload
  | AccessLevelPayload
  | UpdateLevelPayload
  | TransferLevelPayload
  | DeactivateLevelPayload;

export default function CirpassLabPage() {
  const [state, send] = useMachine(cirpassMachine);
  const [layer, setLayer] = useState<'joyful' | 'technical'>('joyful');
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [completedAt, setCompletedAt] = useState<number | null>(null);
  const [clockNow, setClockNow] = useState(() => Date.now());
  const [payloadByLevel, setPayloadByLevel] = useState<Partial<Record<CirpassLevelKey, PayloadShape>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const badgeRef = useRef<HTMLDivElement | null>(null);

  const storiesQuery = useCirpassStories();
  const sessionQuery = useCirpassSession();

  const version = storiesQuery.data?.version ?? 'V3.1';
  const levels = storiesQuery.data?.levels ?? fallbackLevels;
  const { leaderboardQuery, submitMutation } = useCirpassLeaderboard(version, 20);

  const levelValue = resolveCurrentLevel(state.value);
  const completed = levelValue === 'completed';
  const activeLevel: CirpassLevelKey = completed ? 'deactivate' : levelValue;

  useEffect(() => {
    if (completed && completedAt === null) {
      setCompletedAt(Date.now());
    }
  }, [completed, completedAt]);

  useEffect(() => {
    if (completed) {
      return;
    }

    const timer = window.setInterval(() => setClockNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [completed]);

  const elapsedSeconds = Math.max(
    0,
    Math.floor(((completedAt ?? clockNow) - startedAt) / 1000),
  );

  const completedLevels = useMemo(
    () => ({
      create: state.context.levelStats.create.completed,
      access: state.context.levelStats.access.completed,
      update: state.context.levelStats.update.completed,
      transfer: state.context.levelStats.transfer.completed,
      deactivate: state.context.levelStats.deactivate.completed,
    }),
    [state.context.levelStats],
  );

  const scorePreview = computeLoopForgeScore({
    errors: state.context.errors,
    hints: state.context.hints,
    totalSeconds: elapsedSeconds,
    perfectLevels: state.context.perfectLevels,
  });

  const payloadPreview = {
    level: activeLevel,
    payload: payloadByLevel[activeLevel] ?? null,
    metrics: {
      errors: state.context.errors,
      hints: state.context.hints,
      perfectLevels: state.context.perfectLevels,
    },
  };

  const handleSubmitLevel = (level: CirpassLevelKey, payload: PayloadShape) => {
    setPayloadByLevel((prev) => ({ ...prev, [level]: payload }));
    send({ type: 'SUBMIT_LEVEL', level, data: payload });
  };

  const handleHint = (level: CirpassLevelKey) => {
    send({ type: 'HINT_USED', level });
  };

  const handleReset = () => {
    send({ type: 'RESET' });
    setLayer('joyful');
    setPayloadByLevel({});
    setStartedAt(Date.now());
    setCompletedAt(null);
    setSubmitError(null);
    submitMutation.reset();
  };

  const handleSubmitScore = async (nickname: string) => {
    setSubmitError(null);

    if (!sessionQuery.data?.session_token) {
      setSubmitError('Session not initialized. Reload and retry.');
      return;
    }

    try {
      await submitMutation.mutateAsync({
        session_token: sessionQuery.data.session_token,
        nickname,
        score: scorePreview,
        completion_seconds: elapsedSeconds,
        version,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to submit score.';
      setSubmitError(message);
    }
  };

  const handleDownloadBadge = async () => {
    if (!badgeRef.current) {
      return;
    }

    const dataUrl = await htmlToImage.toPng(badgeRef.current, { quality: 0.95, pixelRatio: 2 });
    const anchor = document.createElement('a');
    anchor.href = dataUrl;
    anchor.download = `cirpass-architect-${version.toLowerCase()}.png`;
    anchor.click();
  };

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

        <div className="mt-6 grid gap-5 xl:grid-cols-[1.45fr_0.55fr]">
          <TwinLayerShell
            layer={layer}
            onToggleLayer={() => setLayer((prev) => (prev === 'joyful' ? 'technical' : 'joyful'))}
            joyfulView={
              <JoyfulLayer
                currentLevel={activeLevel}
                completedLevels={completedLevels}
                latestMessage={state.context.lastMessage}
              />
            }
            technicalView={
              <TechnicalLayer
                currentLevel={activeLevel}
                completedLevels={completedLevels}
                payloadPreview={payloadPreview}
              />
            }
          />

          <div className="space-y-5">
            <ScoreHud
              currentLevelLabel={completed ? 'Simulation Completed' : levelLabels[activeLevel]}
              elapsedSeconds={elapsedSeconds}
              errors={state.context.errors}
              hints={state.context.hints}
              perfectLevels={state.context.perfectLevels}
              scorePreview={scorePreview}
            />

            {!completed && (
              <MissionPanel
                currentLevel={activeLevel}
                levels={levels}
                onSubmit={handleSubmitLevel}
                onHint={handleHint}
              />
            )}

            {completed && (
              <section className="rounded-3xl border border-emerald-500/30 bg-emerald-50 p-5">
                <h2 className="font-display text-2xl font-semibold text-emerald-900">
                  Circular loop complete
                </h2>
                <p className="mt-2 text-sm text-emerald-800">
                  Final score: <strong>{scorePreview}</strong> · Time: <strong>{elapsedSeconds}s</strong>
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button type="button" onClick={handleDownloadBadge} data-testid="cirpass-download-badge">
                    Download Architect Badge
                  </Button>
                  <Button type="button" variant="outline" onClick={handleReset} data-testid="cirpass-reset-run">
                    Play Again
                  </Button>
                </div>
              </section>
            )}

            {!completed && (
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={handleReset}
                data-testid="cirpass-reset-run"
              >
                Reset Run
              </Button>
            )}
          </div>
        </div>

        <div className="mt-6">
          <LeaderboardPanel
            completed={completed}
            score={scorePreview}
            elapsedSeconds={elapsedSeconds}
            entries={leaderboardQuery.data?.entries ?? []}
            submitting={submitMutation.isPending}
            submitResult={submitMutation.data ?? null}
            submitError={submitError}
            onSubmit={handleSubmitScore}
          />
        </div>

        <div className="pointer-events-none absolute left-[-9999px] top-[-9999px]" aria-hidden="true">
          <div
            ref={badgeRef}
            className="w-[900px] rounded-[36px] border border-cyan-300/30 bg-slate-950 p-12 text-white"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-cyan-200">LoopForge</p>
            <h2 className="mt-3 font-display text-5xl font-semibold">Certified DPP Architect</h2>
            <p className="mt-3 text-xl text-slate-200">CIRPASS {version}</p>
            <div className="mt-8 grid grid-cols-3 gap-4 text-sm">
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">
                <p className="text-slate-300">Score</p>
                <p className="mt-1 text-3xl font-semibold text-cyan-200">{scorePreview}</p>
              </div>
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">
                <p className="text-slate-300">Elapsed</p>
                <p className="mt-1 text-3xl font-semibold text-cyan-200">{elapsedSeconds}s</p>
              </div>
              <div className="rounded-2xl border border-white/15 bg-white/5 p-4">
                <p className="text-slate-300">Perfect Levels</p>
                <p className="mt-1 text-3xl font-semibold text-cyan-200">{state.context.perfectLevels}</p>
              </div>
            </div>
          </div>
        </div>

        {storiesQuery.isLoading && (
          <p className="mt-5 text-sm text-landing-muted" data-testid="cirpass-loading-feed">
            Loading latest CIRPASS stories...
          </p>
        )}
        {storiesQuery.isError && (
          <p className="mt-5 text-sm text-amber-700" data-testid="cirpass-feed-fallback">
            Live source unavailable. Running on resilient fallback scenarios.
          </p>
        )}
      </div>
    </div>
  );
}
