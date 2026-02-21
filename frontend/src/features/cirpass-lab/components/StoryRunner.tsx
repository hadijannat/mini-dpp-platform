import { useEffect, useMemo, useRef, useState } from 'react';
import { useMachine } from '@xstate/react';
import * as htmlToImage from 'html-to-image';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import type { CirpassLevel } from '@/api/types';
import { cirpassMachine, type CirpassLevelKey } from '../machines/cirpassMachine';
import { computeLoopForgeScore } from '../utils/scoring';
import { useCirpassLeaderboard } from '../hooks/useCirpassLeaderboard';
import { useCirpassLabTelemetry } from '../hooks/useCirpassLabTelemetry';
import { useCirpassManifest } from '../hooks/useCirpassManifest';
import { useStoryProgress } from '../hooks/useStoryProgress';
import { coerceLabMode, coerceLabVariant } from '../schema/manifestLoader';
import type { CirpassLabMode, CirpassLabStep, CirpassLabStory, CirpassLabVariant } from '../schema/storySchema';
import { deriveHintFromFailures, evaluateStepChecks, type CheckResult } from '../utils/checkEngine';
import ApiInspector from './inspectors/ApiInspector';
import ArtifactDiffInspector from './inspectors/ArtifactDiffInspector';
import PolicyInspector from './inspectors/PolicyInspector';
import JoyfulLayer from './JoyfulLayer';
import LeaderboardPanel from './LeaderboardPanel';
import ScoreHud from './ScoreHud';
import StepInteractionRenderer from './StepInteractionRenderer';
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

function getObjective(levels: CirpassLevel[], level: CirpassLevelKey, fallback: string): string {
  return levels.find((entry) => entry.level === level)?.objective ?? fallback;
}

function buildSyntheticFallbackStory(levels: CirpassLevel[], version: string): CirpassLabStory {
  return {
    id: 'fallback-core-loop-v3_1',
    title: 'Fallback Core Lifecycle Loop',
    summary: 'Resilient synthetic flow when remote manifest is unavailable.',
    personas: ['Manufacturer', 'Consumer', 'Repairer', 'Retailer', 'Recycler'],
    learning_goals: [
      'Issue and validate required DPP payload attributes.',
      'Apply role-based access filtering and restricted field controls.',
      'Preserve lifecycle integrity while updates and transfer events occur.',
      'Close end-of-life and recover circularity intelligence.',
    ],
    references: [],
    version,
    steps: [
      {
        id: 'create-passport',
        level: 'create',
        title: 'CREATE passport payload',
        actor: 'Manufacturer',
        intent: getObjective(levels, 'create', 'Build a complete DPP payload with mandatory fields.'),
        actor_goal: 'Publish a valid passport with core sustainability attributes.',
        explanation_md: 'Add identifier, material composition, and carbon footprint before publication.',
        interaction: {
          kind: 'form',
          submit_label: 'Validate & Continue',
          hint_text: 'Include identifier, material composition, and a positive carbon footprint.',
          fields: [
            {
              name: 'identifier',
              label: 'Identifier',
              type: 'text',
              required: true,
              validation: { min_length: 10 },
              test_id: 'cirpass-create-identifier',
            },
            {
              name: 'materialComposition',
              label: 'Material composition',
              type: 'textarea',
              required: true,
              validation: { min_length: 3 },
              test_id: 'cirpass-create-material',
            },
            {
              name: 'carbonFootprint',
              label: 'Carbon footprint (kg CO2e)',
              type: 'number',
              required: true,
              validation: { gt: 0 },
              test_id: 'cirpass-create-carbon',
            },
          ],
          options: [],
        },
        api: {
          method: 'POST',
          path: '/api/v1/tenants/{tenant}/dpps',
          auth: 'user',
          expected_status: 201,
          request_example: {
            identifier: 'did:web:dpp.eu:product:demo-bike',
            materialComposition: 'recycled_aluminum',
            carbonFootprint: 14.2,
          },
          response_example: {
            id: 'dpp_123',
            status: 'active',
          },
        },
        artifacts: {
          before: { status: 'draft', payload: {} },
          after: {
            status: 'active',
            payload: {
              identifier: 'did:web:dpp.eu:product:demo-bike',
              materialComposition: 'recycled_aluminum',
              carbonFootprint: 14.2,
            },
          },
          diff_hint: 'Mandatory fields become available to the technical layer.',
        },
        checks: [
          {
            type: 'schema',
            expression: 'required:create_fields',
            expected: ['identifier', 'materialComposition', 'carbonFootprint'],
          },
        ],
        policy: {
          required_role: 'publisher',
          opa_policy: 'dpp/authz',
          expected_decision: 'allow',
        },
        variants: ['happy'],
      },
      {
        id: 'access-routing',
        level: 'access',
        title: 'ACCESS policy routing',
        actor: 'Authority',
        intent: getObjective(levels, 'access', 'Route role-based views with restricted fields masked.'),
        actor_goal: 'Ensure consumers see public fields while authority checks privileged data.',
        explanation_md: 'Access logic must deny restricted fields to non-authority actors.',
        interaction: {
          kind: 'form',
          submit_label: 'Validate & Continue',
          hint_text: 'Consumer and authority checks must both pass, with restricted data hidden.',
          fields: [
            {
              name: 'consumerViewEnabled',
              label: 'Consumer default access enabled',
              type: 'checkbox',
              required: true,
              validation: { equals: true },
              test_id: 'cirpass-access-consumer',
            },
            {
              name: 'authorityCredentialValidated',
              label: 'Authority credential validated',
              type: 'checkbox',
              required: true,
              validation: { equals: true },
              test_id: 'cirpass-access-authority',
            },
            {
              name: 'restrictedFieldsHiddenFromConsumer',
              label: 'Restricted fields hidden from consumer view',
              type: 'checkbox',
              required: true,
              validation: { equals: true },
              test_id: 'cirpass-access-restricted',
            },
          ],
          options: [],
        },
        api: {
          method: 'GET',
          path: '/api/v1/public/dpps/{id}',
          auth: 'none',
          expected_status: 200,
          response_example: {
            publicFields: ['manual', 'safety'],
          },
        },
        checks: [
          { type: 'status', expected: 200 },
          { type: 'jsonpath', expression: '$.consumerViewEnabled', expected: true },
          { type: 'jsonpath', expression: '$.authorityCredentialValidated', expected: true },
          { type: 'jsonpath', expression: '$.restrictedFieldsHiddenFromConsumer', expected: true },
        ],
        policy: {
          required_role: 'authority',
          opa_policy: 'dpp/authz',
          expected_decision: 'mask',
        },
        variants: ['happy', 'unauthorized', 'not_found'],
      },
      {
        id: 'update-repair-chain',
        level: 'update',
        title: 'UPDATE repair chain',
        actor: 'Repairer',
        intent: getObjective(levels, 'update', 'Append lifecycle updates while preserving provenance.'),
        actor_goal: 'Record a trusted repair event without breaking the hash chain.',
        explanation_md: 'The new hash must differ from the previous hash and include a repair event.',
        interaction: {
          kind: 'form',
          submit_label: 'Validate & Continue',
          hint_text: 'Provide previous hash, new hash, and a non-empty repair event.',
          fields: [
            {
              name: 'previousHash',
              label: 'Previous hash',
              type: 'text',
              required: true,
              validation: { min_length: 8 },
              test_id: 'cirpass-update-prev-hash',
            },
            {
              name: 'newEventHash',
              label: 'New event hash',
              type: 'text',
              required: true,
              validation: { min_length: 8 },
              test_id: 'cirpass-update-new-hash',
            },
            {
              name: 'repairEvent',
              label: 'Repair event',
              type: 'textarea',
              required: true,
              validation: { min_length: 5 },
              test_id: 'cirpass-update-repair-event',
            },
          ],
          options: [],
        },
        api: {
          method: 'PATCH',
          path: '/api/v1/tenants/{tenant}/dpps/{id}',
          auth: 'user',
          expected_status: 200,
        },
        checks: [
          { type: 'jsonpath', expression: '$.previousHash', expected: 'present' },
          { type: 'jsonpath', expression: '$.newEventHash', expected: 'present' },
          { type: 'jsonpath', expression: '$.repairEvent', expected: 'present' },
        ],
        policy: {
          required_role: 'publisher',
          opa_policy: 'dpp/authz',
          expected_decision: 'allow',
        },
        variants: ['happy'],
      },
      {
        id: 'transfer-handoff',
        level: 'transfer',
        title: 'TRANSFER ownership handoff',
        actor: 'Retailer',
        intent: getObjective(levels, 'transfer', 'Transfer ownership while preserving confidentiality.'),
        actor_goal: 'Handoff custody while keeping restricted fields protected.',
        explanation_md: 'From and to actors must differ while confidentiality remains enabled.',
        interaction: {
          kind: 'form',
          submit_label: 'Validate & Continue',
          hint_text: 'Use different actors and keep confidentiality enabled.',
          fields: [
            {
              name: 'fromActor',
              label: 'From actor',
              type: 'text',
              required: true,
              validation: { min_length: 2 },
              test_id: 'cirpass-transfer-from',
            },
            {
              name: 'toActor',
              label: 'To actor',
              type: 'text',
              required: true,
              validation: { min_length: 2 },
              test_id: 'cirpass-transfer-to',
            },
            {
              name: 'confidentialityMaintained',
              label: 'Confidentiality boundary preserved',
              type: 'checkbox',
              required: true,
              validation: { equals: true },
              test_id: 'cirpass-transfer-confidentiality',
            },
          ],
          options: [],
        },
        api: {
          method: 'POST',
          path: '/api/v1/tenants/{tenant}/shares',
          auth: 'user',
          expected_status: 201,
        },
        checks: [
          { type: 'status', expected: 201 },
          { type: 'jsonpath', expression: '$.fromActor', expected: 'present' },
          { type: 'jsonpath', expression: '$.toActor', expected: 'present' },
          { type: 'jsonpath', expression: '$.confidentialityMaintained', expected: true },
        ],
        policy: {
          required_role: 'publisher',
          opa_policy: 'dpp/authz',
          expected_decision: 'allow',
        },
        variants: ['happy'],
      },
      {
        id: 'deactivate-loop',
        level: 'deactivate',
        title: 'DEACTIVATE and circular loop closure',
        actor: 'Recycler',
        intent: getObjective(levels, 'deactivate', 'Mark end-of-life and expose recovered outputs.'),
        actor_goal: 'Close lifecycle and feed recovered insights into the next passport.',
        explanation_md: 'End-of-life requires recovered materials and next-passport spawn.',
        interaction: {
          kind: 'form',
          submit_label: 'Validate & Continue',
          hint_text: 'Set status to end_of_life and include recovered materials.',
          fields: [
            {
              name: 'lifecycleStatus',
              label: 'Lifecycle status',
              type: 'select',
              required: true,
              options: [
                { label: 'active', value: 'active' },
                { label: 'end_of_life', value: 'end_of_life' },
              ],
              validation: { equals: 'end_of_life' },
              test_id: 'cirpass-deactivate-status',
            },
            {
              name: 'recoveredMaterials',
              label: 'Recovered materials',
              type: 'textarea',
              required: true,
              validation: { min_length: 3 },
              test_id: 'cirpass-deactivate-materials',
            },
            {
              name: 'spawnNextPassport',
              label: 'Spawn material insight for next passport',
              type: 'checkbox',
              required: true,
              validation: { equals: true },
              test_id: 'cirpass-deactivate-spawn',
            },
          ],
          options: [],
        },
        api: {
          method: 'POST',
          path: '/api/v1/tenants/{tenant}/dpps/{id}/lifecycle',
          auth: 'user',
          expected_status: 200,
          response_example: {
            status: 'end_of_life',
          },
        },
        checks: [
          { type: 'jsonpath', expression: '$.lifecycleStatus', expected: 'end_of_life' },
          { type: 'jsonpath', expression: '$.recoveredMaterials', expected: 'present' },
          { type: 'jsonpath', expression: '$.spawnNextPassport', expected: true },
        ],
        policy: {
          required_role: 'recycler',
          opa_policy: 'dpp/authz',
          expected_decision: 'allow',
        },
        variants: ['happy'],
      },
    ],
  };
}

function resolveStepStatus(step: CirpassLabStep, variant: CirpassLabVariant): number {
  if (variant === 'unauthorized') {
    return 403;
  }
  if (variant === 'not_found') {
    return 404;
  }
  return step.api?.expected_status ?? 200;
}

function buildResponseBody(step: CirpassLabStep, payload: Record<string, unknown>): Record<string, unknown> {
  const response = { ...payload };
  if (step.level === 'deactivate' && typeof payload.lifecycleStatus === 'string') {
    response.status = payload.lifecycleStatus;
  }
  return response;
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
  const [payloadByStep, setPayloadByStep] = useState<Record<string, Record<string, unknown>>>({});
  const [checkResultByStep, setCheckResultByStep] = useState<Record<string, CheckResult>>({});
  const [responseByStep, setResponseByStep] = useState<Record<string, { status: number; body?: unknown }>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [shareCopied, setShareCopied] = useState(false);
  const [stepFeedback, setStepFeedback] = useState<string | null>(null);
  const badgeRef = useRef<HTMLDivElement | null>(null);

  const [searchParams, setSearchParams] = useSearchParams();
  const mode = coerceLabMode(searchParams.get('mode'));
  const variant = coerceLabVariant(searchParams.get('variant'));
  const { storyId: storyIdParam, stepId: stepIdParam } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const manifestQuery = useCirpassManifest();
  const manifestEnvelope = manifestQuery.data;
  const manifest = manifestEnvelope?.manifest;

  const { leaderboardQuery, submitMutation } = useCirpassLeaderboard(version, 20);
  const { trackEvent } = useCirpassLabTelemetry();

  const scenarioEngineEnabled =
    manifest?.feature_flags.scenario_engine_enabled === true &&
    (manifest.stories.length ?? 0) > 0;

  const syntheticFallbackStory = useMemo(
    () => buildSyntheticFallbackStory(levels, version),
    [levels, version],
  );

  const selectedStory = useMemo(() => {
    if (!scenarioEngineEnabled || !manifest) {
      return syntheticFallbackStory;
    }

    if (storyIdParam) {
      const direct = manifest.stories.find((story) => story.id === storyIdParam);
      if (direct) {
        return direct;
      }
    }
    return manifest.stories[0] ?? syntheticFallbackStory;
  }, [manifest, scenarioEngineEnabled, storyIdParam, syntheticFallbackStory]);

  const progress = useStoryProgress(selectedStory.id);

  const activeStepIndex = useMemo(() => {
    if (selectedStory.steps.length === 0) {
      return 0;
    }
    return Math.min(state.context.currentStepIndex, selectedStory.steps.length - 1);
  }, [selectedStory.steps.length, state.context.currentStepIndex]);

  const activeStep = selectedStory.steps[activeStepIndex] ?? selectedStory.steps[0];
  const completed = state.matches('completed');
  const activeLevel = activeStep?.level ?? 'create';

  const completedLevelKeys = useMemo(
    () => levelOrder.filter((level) => state.context.levelStats[level]?.completed),
    [state.context.levelStats],
  );

  const manifestFallbackWarning = useMemo(() => {
    if (manifestQuery.isError) {
      return 'Scenario manifest unavailable. Running fallback 5-level flow.';
    }
    if (manifestEnvelope?.resolved_from === 'generated') {
      return manifestEnvelope.warning ?? 'Using bundled scenario manifest.';
    }
    if (manifest && !scenarioEngineEnabled) {
      return 'Scenario engine disabled by feature flag. Running fallback 5-level flow.';
    }
    return null;
  }, [manifest, manifestEnvelope, manifestQuery.isError, scenarioEngineEnabled]);

  const emitTelemetry = (
    eventType: 'step_view' | 'step_submit' | 'hint' | 'mode_switch' | 'reset_story' | 'reset_all',
    result: 'success' | 'error' | 'info',
    metadata: Record<string, unknown> = {},
    latencyMs?: number,
  ) => {
    if (!sessionToken || !activeStep) {
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
    const currentKey = `${selectedStory.id}:${stepIdParam ?? ''}`;
    if (restoreKeyRef.current === currentKey) {
      return;
    }
    restoreKeyRef.current = currentKey;

    const saved = progress.loadProgress();
    const routeStep = stepIdParam
      ? selectedStory.steps.find((step) => step.id === stepIdParam)
      : null;
    const savedStep =
      !routeStep && saved?.step_id
        ? selectedStory.steps.find((step) => step.id === saved.step_id)
        : null;
    const targetStep = routeStep ?? savedStep ?? selectedStory.steps[0] ?? null;
    const completedLevels = routeStep ? [] : saved?.completed_levels ?? [];

    send({
      type: 'INIT',
      steps: selectedStory.steps.map((step) => ({ id: step.id, level: step.level })),
      startStepId: targetStep?.id ?? selectedStory.steps[0]?.id ?? null,
      completedLevels,
    });
    setLayer('joyful');
    setPayloadByStep({});
    setCheckResultByStep({});
    setResponseByStep({});
    setStartedAt(Date.now());
    setCompletedAt(null);
    setSubmitError(null);
    setStepFeedback(null);
    submitMutation.reset();

    if (!searchParams.get('mode') || !searchParams.get('variant')) {
      const nextSearch = new URLSearchParams(searchParams);
      nextSearch.set('mode', saved?.mode ?? mode);
      nextSearch.set('variant', saved?.variant ?? variant);
      setSearchParams(nextSearch, { replace: true });
    }
  }, [
    mode,
    progress,
    searchParams,
    selectedStory.id,
    selectedStory.steps,
    send,
    setSearchParams,
    stepIdParam,
    submitMutation,
    variant,
  ]);

  useEffect(() => {
    if (!activeStep) {
      return;
    }

    if (!activeStep.variants.includes(variant)) {
      const nextSearch = new URLSearchParams(searchParams);
      nextSearch.set('mode', mode);
      nextSearch.set('variant', activeStep.variants[0] ?? 'happy');
      setSearchParams(nextSearch, { replace: true });
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
    searchParams,
    selectedStory.id,
    setSearchParams,
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
  const scorePreview = computeLoopForgeScore({
    errors: state.context.errors,
    hints: state.context.hints,
    totalSeconds: elapsedSeconds,
    perfectLevels: state.context.perfectLevels,
  });

  const currentObjective = getObjective(levels, activeLevel, activeStep?.intent ?? '');
  const currentPayloadPreview = activeStep ? payloadByStep[activeStep.id] ?? null : null;
  const currentCheckResult = activeStep ? checkResultByStep[activeStep.id] ?? null : null;
  const currentResponsePreview = activeStep ? responseByStep[activeStep.id] ?? null : null;

  const derivedHint = useMemo(() => {
    if (!activeStep) {
      return 'Review step details and technical checks.';
    }
    if (activeStep.interaction?.hint_text) {
      return activeStep.interaction.hint_text;
    }
    return deriveHintFromFailures(currentCheckResult?.failures ?? []);
  }, [activeStep, currentCheckResult?.failures]);

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

  const handleSubmitLevel = (payload: Record<string, unknown>) => {
    if (!activeStep) {
      return;
    }
    const started = Date.now();
    const status = resolveStepStatus(activeStep, variant);
    const responseBody = buildResponseBody(activeStep, payload);
    const checkResult = evaluateStepChecks(activeStep, {
      payload,
      response_status: status,
      response_body: responseBody,
      mode,
      variant,
    });

    setPayloadByStep((prev) => ({ ...prev, [activeStep.id]: payload }));
    setResponseByStep((prev) => ({ ...prev, [activeStep.id]: { status, body: responseBody } }));
    setCheckResultByStep((prev) => ({ ...prev, [activeStep.id]: checkResult }));
    setStepFeedback(
      checkResult.passed
        ? activeStep.interaction?.success_message ?? `${activeStep.level.toUpperCase()} step passed.`
        : activeStep.interaction?.failure_message ?? deriveHintFromFailures(checkResult.failures),
    );

    send({
      type: 'SUBMIT_STEP',
      stepId: activeStep.id,
      level: activeStep.level,
      isValid: checkResult.passed,
    });

    emitTelemetry(
      'step_submit',
      checkResult.passed ? 'success' : 'error',
      { level: activeStep.level, variant },
      Date.now() - started,
    );
  };

  const handleHint = () => {
    if (!activeStep) {
      return;
    }
    send({ type: 'HINT_USED', stepId: activeStep.id, level: activeStep.level });
    setStepFeedback(derivedHint);
    emitTelemetry('hint', 'info', { level: activeStep.level });
  };

  const handleReset = () => {
    send({ type: 'RESET' });
    setLayer('joyful');
    setPayloadByStep({});
    setCheckResultByStep({});
    setResponseByStep({});
    setStartedAt(Date.now());
    setCompletedAt(null);
    setSubmitError(null);
    setStepFeedback(null);
    submitMutation.reset();
  };

  const handleResetStory = () => {
    progress.resetStory();
    handleReset();
    emitTelemetry('reset_story', 'info', { source: 'reset-story' });
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
    if (!activeStep) {
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

  const liveModeEnabled = manifest?.feature_flags.live_mode_enabled ?? false;
  const inspectorEnabled = manifest?.feature_flags.inspector_enabled ?? true;

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
            const nextLayer = layer === 'joyful' ? 'technical' : 'joyful';
            setLayer(nextLayer);
            emitTelemetry('mode_switch', 'info', {
              from: layer,
              to: nextLayer,
            });
          }}
          joyfulView={
            <JoyfulLayer
              currentLevel={activeLevel}
              completedLevels={completedLevels}
              latestMessage={state.context.lastMessage}
              story={selectedStory}
              step={activeStep}
            />
          }
          technicalView={
            <TechnicalLayer
              currentLevel={activeLevel}
              completedLevels={completedLevels}
              story={selectedStory}
              step={activeStep}
              payloadPreview={currentPayloadPreview}
              responsePreview={currentResponsePreview}
              checkResult={currentCheckResult}
            />
          }
        />

        <div className="space-y-5">
          <ScoreHud
            currentLevelLabel={
              completed
                ? 'Simulation Completed'
                : `${levelLabels[activeLevel]} · Step ${activeStepIndex + 1}/${selectedStory.steps.length}`
            }
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
                    next.set('mode', nextMode === 'live' && !liveModeEnabled ? 'mock' : nextMode);
                    next.set('variant', variant);
                    setSearchParams(next, { replace: true });
                  }}
                  className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-normal normal-case tracking-normal text-foreground"
                  data-testid="cirpass-mode-select"
                >
                  <option value="mock">mock (recommended)</option>
                  <option value="live" disabled={!liveModeEnabled}>
                    live {liveModeEnabled ? '' : '(disabled)'}
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
              {stepFeedback && (
                <p className="rounded-xl border border-landing-ink/12 bg-landing-surface-0/70 px-3 py-2 text-xs font-medium text-landing-ink">
                  {stepFeedback}
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
          </section>

          {!completed && (
            <StepInteractionRenderer
              step={activeStep}
              objective={currentObjective}
              derivedHint={derivedHint}
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

      {inspectorEnabled && (
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

      <p className="mt-4 break-all text-xs text-landing-muted">
        Deep link:{' '}
        <Link
          to={`/cirpass-lab/story/${selectedStory.id}/step/${activeStep?.id ?? selectedStory.steps[0]?.id}?mode=${mode}&variant=${variant}`}
          className="underline break-all"
        >
          /cirpass-lab/story/{selectedStory.id}/step/{activeStep?.id ?? selectedStory.steps[0]?.id}
        </Link>
      </p>
    </>
  );
}
