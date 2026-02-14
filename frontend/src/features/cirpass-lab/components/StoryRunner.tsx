import { useEffect, useMemo, useRef, useState } from 'react';
import { useMachine } from '@xstate/react';
import * as htmlToImage from 'html-to-image';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
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
import { useCirpassLabTelemetry } from '../hooks/useCirpassLabTelemetry';
import { useCirpassManifest } from '../hooks/useCirpassManifest';
import { useStoryProgress } from '../hooks/useStoryProgress';
import {
  coerceLabMode,
  coerceLabVariant,
  mapStoryStepsByLevel,
} from '../schema/manifestLoader';
import type { CirpassLabMode, CirpassLabVariant } from '../schema/storySchema';
import ApiInspector from './inspectors/ApiInspector';
import ArtifactDiffInspector from './inspectors/ArtifactDiffInspector';
import PolicyInspector from './inspectors/PolicyInspector';
import JoyfulLayer from './JoyfulLayer';
import LeaderboardPanel from './LeaderboardPanel';
import MissionPanel from './MissionPanel';
import ScoreHud from './ScoreHud';
import TechnicalLayer from './TechnicalLayer';
import TwinLayerShell from './TwinLayerShell';

const levelLabels: Record<CirpassLevelKey, string> = {
  create: 'Level 1 · CREATE',
  access: 'Level 2 · ACCESS',
  update: 'Level 3 · UPDATE',
  transfer: 'Level 4 · TRANSFER',
  deactivate: 'Level 5 · DEACTIVATE',
};

const levelOrder: CirpassLevelKey[] = ['create', 'access', 'update', 'transfer', 'deactivate'];

const validPayloadByLevel: Record<
  CirpassLevelKey,
  CreateLevelPayload | AccessLevelPayload | UpdateLevelPayload | TransferLevelPayload | DeactivateLevelPayload
> = {
  create: {
    identifier: 'did:web:dpp.eu:product:seeded-demo',
    materialComposition: 'recycled_aluminum',
    carbonFootprint: 12.2,
  },
  access: {
    consumerViewEnabled: true,
    authorityCredentialValidated: true,
    restrictedFieldsHiddenFromConsumer: true,
  },
  update: {
    previousHash: 'prevhash-seeded-0001',
    newEventHash: 'newhash-seeded-0002',
    repairEvent: 'Repair event replayed from saved progress.',
  },
  transfer: {
    fromActor: 'Seeded Wholesaler',
    toActor: 'Seeded Retailer',
    confidentialityMaintained: true,
  },
  deactivate: {
    lifecycleStatus: 'end_of_life',
    recoveredMaterials: 'copper, lithium, aluminum',
    spawnNextPassport: true,
  },
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

function validatePayload(level: CirpassLevelKey, payload: PayloadShape): boolean {
  if (level === 'create') {
    const source = payload as CreateLevelPayload;
    const identifier = source.identifier?.trim() ?? '';
    const materialComposition = source.materialComposition?.trim() ?? '';
    return (
      identifier.length > 0 &&
      materialComposition.length > 0 &&
      typeof source.carbonFootprint === 'number' &&
      source.carbonFootprint > 0
    );
  }

  if (level === 'access') {
    const source = payload as AccessLevelPayload;
    return (
      source.consumerViewEnabled === true &&
      source.authorityCredentialValidated === true &&
      source.restrictedFieldsHiddenFromConsumer === true
    );
  }

  if (level === 'update') {
    const source = payload as UpdateLevelPayload;
    const previousHash = source.previousHash?.trim() ?? '';
    const newEventHash = source.newEventHash?.trim() ?? '';
    const repairEvent = source.repairEvent?.trim() ?? '';
    return (
      previousHash.length > 6 &&
      newEventHash.length > 6 &&
      previousHash !== newEventHash &&
      repairEvent.length > 0
    );
  }

  if (level === 'transfer') {
    const source = payload as TransferLevelPayload;
    const fromActor = source.fromActor?.trim() ?? '';
    const toActor = source.toActor?.trim() ?? '';
    return fromActor.length > 0 && toActor.length > 0 && fromActor !== toActor && source.confidentialityMaintained;
  }

  const source = payload as DeactivateLevelPayload;
  const recovered = source.recoveredMaterials?.trim() ?? '';
  return source.lifecycleStatus === 'end_of_life' && recovered.length > 0 && source.spawnNextPassport;
}

interface StoryRunnerProps {
  version: string;
  levels: CirpassLevel[];
  sourceStatus: 'fresh' | 'stale' | undefined;
  storiesLoading: boolean;
  storiesError: boolean;
  sessionToken: string | null;
}

export default function StoryRunner({
  version,
  levels,
  sourceStatus,
  storiesLoading,
  storiesError,
  sessionToken,
}: StoryRunnerProps) {
  const [state, send] = useMachine(cirpassMachine);
  const [layer, setLayer] = useState<'joyful' | 'technical'>('joyful');
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [completedAt, setCompletedAt] = useState<number | null>(null);
  const [clockNow, setClockNow] = useState(() => Date.now());
  const [payloadByLevel, setPayloadByLevel] = useState<Partial<Record<CirpassLevelKey, PayloadShape>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [shareCopied, setShareCopied] = useState(false);
  const badgeRef = useRef<HTMLDivElement | null>(null);

  const [searchParams, setSearchParams] = useSearchParams();
  const mode = coerceLabMode(searchParams.get('mode'));
  const variant = coerceLabVariant(searchParams.get('variant'));
  const { storyId: storyIdParam, stepId: stepIdParam } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const manifestQuery = useCirpassManifest();
  const { leaderboardQuery, submitMutation } = useCirpassLeaderboard(version, 20);
  const { trackEvent } = useCirpassLabTelemetry();

  const scenarioEngineEnabled =
    manifestQuery.data?.feature_flags.scenario_engine_enabled === true &&
    (manifestQuery.data?.stories.length ?? 0) > 0;

  const selectedStory = useMemo(() => {
    if (!scenarioEngineEnabled || !manifestQuery.data) {
      return null;
    }

    const allStories = manifestQuery.data.stories;
    if (storyIdParam) {
      const byParam = allStories.find((story) => story.id === storyIdParam);
      if (byParam) {
        return byParam;
      }
    }
    return allStories[0] ?? null;
  }, [manifestQuery.data, scenarioEngineEnabled, storyIdParam]);

  const progress = useStoryProgress(selectedStory?.id ?? '');
  const storyStepsByLevel = useMemo(
    () => (selectedStory ? mapStoryStepsByLevel(selectedStory.steps) : null),
    [selectedStory],
  );

  const levelValue = resolveCurrentLevel(state.value);
  const completed = levelValue === 'completed';
  const activeLevel: CirpassLevelKey = completed ? 'deactivate' : levelValue;
  const activeStep = selectedStory && storyStepsByLevel ? storyStepsByLevel[activeLevel] : null;

  const completedLevelKeys = useMemo(
    () => levelOrder.filter((level) => state.context.levelStats[level].completed),
    [state.context.levelStats],
  );

  const manifestFallbackWarning = useMemo(() => {
    if (manifestQuery.isError) {
      return 'Scenario manifest unavailable. Running fallback 5-level flow.';
    }
    if (manifestQuery.data && !scenarioEngineEnabled) {
      return 'Scenario engine disabled by feature flag. Running fallback 5-level flow.';
    }
    return null;
  }, [manifestQuery.data, manifestQuery.isError, scenarioEngineEnabled]);

  const emitTelemetry = (
    eventType: 'step_view' | 'step_submit' | 'hint' | 'mode_switch' | 'reset_story' | 'reset_all',
    result: 'success' | 'error' | 'info',
    metadata: Record<string, unknown> = {},
    latencyMs?: number,
  ) => {
    if (!sessionToken || !selectedStory || !activeStep) {
      return;
    }

    trackEvent({
      session_token: sessionToken,
      story_id: selectedStory.id,
      step_id: activeStep.id,
      event_type: eventType,
      mode,
      variant,
      result,
      latency_ms: latencyMs,
      metadata,
    });
  };

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

  const restoreKeyRef = useRef<string>('');
  useEffect(() => {
    if (!scenarioEngineEnabled || !selectedStory) {
      return;
    }

    const currentKey = `${selectedStory.id}:${stepIdParam ?? ''}`;
    if (restoreKeyRef.current === currentKey) {
      return;
    }
    restoreKeyRef.current = currentKey;

    const saved = progress.loadProgress();
    const routeStep = stepIdParam ? selectedStory.steps.find((step) => step.id === stepIdParam) : null;
    const savedStep =
      !routeStep && saved?.step_id
        ? selectedStory.steps.find((step) => step.id === saved.step_id)
        : null;
    const targetStep = routeStep ?? savedStep ?? selectedStory.steps[0] ?? null;

    send({ type: 'RESET' });
    setLayer('joyful');
    setPayloadByLevel({});
    setStartedAt(Date.now());
    setCompletedAt(null);
    setSubmitError(null);
    submitMutation.reset();

    if (!targetStep) {
      return;
    }

    const targetIndex = selectedStory.steps.findIndex((step) => step.id === targetStep.id);
    const replaySteps = selectedStory.steps.slice(0, Math.max(0, targetIndex));

    for (const step of replaySteps) {
      send({ type: 'SUBMIT_LEVEL', level: step.level, data: validPayloadByLevel[step.level] });
      setPayloadByLevel((prev) => ({ ...prev, [step.level]: validPayloadByLevel[step.level] }));
    }

    if (!searchParams.get('mode') || !searchParams.get('variant')) {
      const nextSearch = new URLSearchParams(searchParams);
      nextSearch.set('mode', saved?.mode ?? mode);
      nextSearch.set('variant', saved?.variant ?? variant);
      setSearchParams(nextSearch, { replace: true });
    }
  }, [
    mode,
    progress,
    scenarioEngineEnabled,
    searchParams,
    selectedStory,
    send,
    setSearchParams,
    stepIdParam,
    submitMutation,
    variant,
  ]);

  useEffect(() => {
    if (!scenarioEngineEnabled || !selectedStory || !activeStep) {
      return;
    }

    const nextSearch = new URLSearchParams(searchParams);
    nextSearch.set('mode', mode);
    nextSearch.set('variant', variant);
    const targetPath = `/cirpass-lab/story/${selectedStory.id}/step/${activeStep.id}`;
    const targetSearch = `?${nextSearch.toString()}`;

    if (location.pathname !== targetPath || location.search !== targetSearch) {
      navigate(`${targetPath}${targetSearch}`, { replace: true });
    }

    progress.saveProgress({
      step_id: activeStep.id,
      completed_levels: completedLevelKeys,
      mode,
      variant,
    });
  }, [
    activeStep,
    completedLevelKeys,
    location.pathname,
    location.search,
    mode,
    navigate,
    progress,
    scenarioEngineEnabled,
    searchParams,
    selectedStory,
    variant,
  ]);

  useEffect(() => {
    if (!activeStep) {
      return;
    }
    emitTelemetry('step_view', 'info', {
      level: activeLevel,
      layer,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStep?.id, activeLevel, layer, mode, variant]);

  const elapsedSeconds = Math.max(0, Math.floor(((completedAt ?? clockNow) - startedAt) / 1000));

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
    scenario: selectedStory?.id ?? null,
    step: activeStep?.id ?? null,
  };

  const handleSubmitLevel = (level: CirpassLevelKey, payload: PayloadShape) => {
    const started = Date.now();
    const isValid = validatePayload(level, payload);
    setPayloadByLevel((prev) => ({ ...prev, [level]: payload }));
    send({ type: 'SUBMIT_LEVEL', level, data: payload });

    emitTelemetry('step_submit', isValid ? 'success' : 'error', { level, variant }, Date.now() - started);
  };

  const handleHint = (level: CirpassLevelKey) => {
    send({ type: 'HINT_USED', level });
    emitTelemetry('hint', 'info', { level });
  };

  const handleReset = () => {
    send({ type: 'RESET' });
    setLayer('joyful');
    setPayloadByLevel({});
    setStartedAt(Date.now());
    setCompletedAt(null);
    setSubmitError(null);
    submitMutation.reset();
    emitTelemetry('reset_story', 'info', { source: 'reset-run' });
  };

  const handleResetStory = () => {
    progress.resetStory();
    handleReset();
  };

  const handleResetAll = () => {
    progress.resetAll();
    handleReset();
    emitTelemetry('reset_all', 'info', { scope: 'all-stories' });
  };

  const handleSubmitScore = async (nickname: string) => {
    setSubmitError(null);

    if (!sessionToken) {
      setSubmitError('Session not initialized. Reload and retry.');
      return;
    }

    try {
      await submitMutation.mutateAsync({
        session_token: sessionToken,
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

  const handleCopyStepLink = async () => {
    if (!selectedStory || !activeStep) {
      return;
    }
    const url = `${window.location.origin}/cirpass-lab/story/${selectedStory.id}/step/${activeStep.id}?mode=${mode}&variant=${variant}`;
    await navigator.clipboard.writeText(url);
    setShareCopied(true);
    window.setTimeout(() => setShareCopied(false), 1200);
  };

  const variantGuidance =
    variant === 'unauthorized'
      ? 'Unauthorized variant active: expect policy-deny behavior and masked restricted fields.'
      : variant === 'not_found'
        ? 'Not-found variant active: expect resolver miss handling and graceful fallback guidance.'
        : null;

  const availableVariants: CirpassLabVariant[] =
    activeStep && activeStep.variants.length > 0
      ? activeStep.variants
      : ['happy', 'unauthorized', 'not_found'];

  return (
    <>
      {manifestFallbackWarning && (
        <div className="mt-4 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800" data-testid="cirpass-manifest-fallback">
          {manifestFallbackWarning}
        </div>
      )}

      <div className="mt-6 grid gap-5 xl:grid-cols-[1.45fr_0.55fr]">
        <TwinLayerShell
          layer={layer}
          onToggleLayer={() => {
            setLayer((prev) => (prev === 'joyful' ? 'technical' : 'joyful'));
            emitTelemetry('mode_switch', 'info', {
              from: layer,
              to: layer === 'joyful' ? 'technical' : 'joyful',
            });
          }}
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

          <section className="rounded-3xl border border-landing-ink/15 bg-white/85 p-5 shadow-[0_24px_40px_-34px_rgba(17,37,49,0.65)]">
            <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">
              Scenario Runner
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-semibold uppercase tracking-[0.1em] text-landing-muted">
                Mode
                <select
                  value={mode}
                  onChange={(event) => {
                    const nextMode = event.target.value as CirpassLabMode;
                    const next = new URLSearchParams(searchParams);
                    next.set('mode', nextMode === 'live' && !manifestQuery.data?.feature_flags.live_mode_enabled ? 'mock' : nextMode);
                    next.set('variant', variant);
                    setSearchParams(next, { replace: true });
                  }}
                  className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-normal normal-case tracking-normal text-foreground"
                  data-testid="cirpass-mode-select"
                >
                  <option value="mock">mock (recommended)</option>
                  <option value="live" disabled={!manifestQuery.data?.feature_flags.live_mode_enabled}>
                    live {manifestQuery.data?.feature_flags.live_mode_enabled ? '' : '(disabled)'}
                  </option>
                </select>
              </label>

              <label className="text-xs font-semibold uppercase tracking-[0.1em] text-landing-muted">
                Variant
                <select
                  value={variant}
                  onChange={(event) => {
                    const next = new URLSearchParams(searchParams);
                    next.set('mode', mode);
                    next.set('variant', event.target.value as CirpassLabVariant);
                    setSearchParams(next, { replace: true });
                  }}
                  className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-normal normal-case tracking-normal text-foreground"
                  data-testid="cirpass-variant-select"
                >
                  {availableVariants.map((variantOption) => (
                    <option key={variantOption} value={variantOption}>
                      {variantOption}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {scenarioEngineEnabled && selectedStory && activeStep ? (
              <div className="mt-4 space-y-2 text-sm">
                <p className="font-semibold text-landing-ink">{selectedStory.title}</p>
                <p className="text-landing-muted">
                  Step: <span className="font-semibold text-landing-ink">{activeStep.title}</span> · Actor:{' '}
                  {activeStep.actor}
                </p>
                <p className="text-landing-muted">{activeStep.explanation_md}</p>
                {variantGuidance && (
                  <p className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800" data-testid="cirpass-variant-guidance">
                    {variantGuidance}
                  </p>
                )}
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button type="button" variant="outline" className="rounded-full px-4" onClick={handleCopyStepLink} data-testid="cirpass-copy-step-link">
                    {shareCopied ? 'Link copied' : 'Copy step link'}
                  </Button>
                  <Button type="button" variant="outline" className="rounded-full px-4" onClick={handleResetStory} data-testid="cirpass-reset-story">
                    Reset story
                  </Button>
                  <Button type="button" variant="outline" className="rounded-full px-4" onClick={handleResetAll} data-testid="cirpass-reset-all">
                    Reset all
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-landing-muted">Fallback runner active with base lifecycle objectives.</p>
            )}
          </section>

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

      {scenarioEngineEnabled && manifestQuery.data?.feature_flags.inspector_enabled && (
        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          <ApiInspector api={activeStep?.api} mode={mode} variant={variant} />
          <ArtifactDiffInspector artifacts={activeStep?.artifacts} />
          <PolicyInspector policy={activeStep?.policy} variant={variant} />
        </div>
      )}

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

      <div className="pointer-events-none fixed left-[-9999px] top-0" aria-hidden="true">
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

      {storiesLoading && (
        <p className="mt-5 text-sm text-landing-muted" data-testid="cirpass-loading-feed">
          Loading latest CIRPASS stories...
        </p>
      )}
      {storiesError && (
        <p className="mt-5 text-sm text-amber-700" data-testid="cirpass-feed-fallback">
          Live source unavailable. Running on resilient fallback scenarios.
        </p>
      )}
      {sourceStatus === 'stale' && (
        <p className="mt-3 text-xs font-semibold uppercase tracking-[0.1em] text-amber-700">
          Source is stale while refresh is running.
        </p>
      )}

      {scenarioEngineEnabled && selectedStory && (
        <p className="mt-4 break-all text-xs text-landing-muted">
          Deep link:{' '}
          <Link
            to={`/cirpass-lab/story/${selectedStory.id}/step/${activeStep?.id ?? selectedStory.steps[0]?.id}?mode=${mode}&variant=${variant}`}
            className="underline break-all"
          >
            /cirpass-lab/story/{selectedStory.id}/step/{activeStep?.id ?? selectedStory.steps[0]?.id}
          </Link>
        </p>
      )}
    </>
  );
}
