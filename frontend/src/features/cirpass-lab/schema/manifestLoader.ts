import { ZodError } from 'zod';
import { generatedCirpassManifest } from '../stories.generated';
import {
  cirpassLabManifestSchema,
  cirpassLabModeSchema,
  cirpassLabVariantSchema,
  cirpassLevelKeySchema,
  type CirpassLabManifest,
  type CirpassLabMode,
  type CirpassLabStep,
  type CirpassLabVariant,
  type CirpassLevelKey,
} from './storySchema';

function formatParseError(error: ZodError): string {
  return error.issues
    .map((issue) => {
      const path = issue.path.join('.');
      return path ? `${path}: ${issue.message}` : issue.message;
    })
    .join('; ');
}

export function parseCirpassLabManifest(input: unknown): CirpassLabManifest {
  const normalized = normalizeManifest(input);
  const parsed = cirpassLabManifestSchema.safeParse(normalized);
  if (!parsed.success) {
    throw new Error(`Invalid CIRPASS lab manifest payload: ${formatParseError(parsed.error)}`);
  }
  return parsed.data;
}

export function loadGeneratedCirpassManifest(): CirpassLabManifest {
  return parseCirpassLabManifest(generatedCirpassManifest);
}

export function coerceLabMode(input: string | null | undefined): CirpassLabMode {
  const parsed = cirpassLabModeSchema.safeParse((input ?? '').trim());
  return parsed.success ? parsed.data : 'mock';
}

export function coerceLabVariant(input: string | null | undefined): CirpassLabVariant {
  const parsed = cirpassLabVariantSchema.safeParse((input ?? '').trim());
  return parsed.success ? parsed.data : 'happy';
}

export function isLevelKey(value: string | null | undefined): value is CirpassLevelKey {
  if (!value) {
    return false;
  }
  return cirpassLevelKeySchema.safeParse(value).success;
}

export function mapStoryStepsByLevel(storySteps: CirpassLabStep[]): Record<CirpassLevelKey, CirpassLabStep | null> {
  const mapped: Record<CirpassLevelKey, CirpassLabStep | null> = {
    create: null,
    access: null,
    update: null,
    transfer: null,
    deactivate: null,
  };

  for (const step of storySteps) {
    if (!mapped[step.level]) {
      mapped[step.level] = step;
    }
  }

  return mapped;
}

function normalizeManifest(input: unknown): unknown {
  if (!input || typeof input !== 'object') {
    return input;
  }

  const source = input as Record<string, unknown>;
  if (!Array.isArray(source.stories)) {
    return input;
  }

  return {
    ...source,
    stories: source.stories.map((story) => normalizeStory(story)),
  };
}

function normalizeStory(story: unknown): unknown {
  if (!story || typeof story !== 'object') {
    return story;
  }

  const source = story as Record<string, unknown>;
  if (!Array.isArray(source.steps)) {
    return story;
  }

  return {
    ...source,
    steps: source.steps.map((step) => normalizeStep(step)),
  };
}

function normalizeStep(step: unknown): unknown {
  if (!step || typeof step !== 'object') {
    return step;
  }

  const source = step as Record<string, unknown>;
  const interaction = normalizeInteraction(source.interaction, source.ui_action);
  return {
    ...source,
    interaction,
  };
}

function normalizeInteraction(
  interaction: unknown,
  uiAction: unknown,
): Record<string, unknown> | unknown {
  if (interaction && typeof interaction === 'object') {
    const source = interaction as Record<string, unknown>;
    return {
      ...source,
      kind: typeof source.kind === 'string' ? source.kind : 'form',
      submit_label:
        typeof source.submit_label === 'string' && source.submit_label.trim().length > 0
          ? source.submit_label
          : inferLegacySubmitLabel(uiAction),
      fields: Array.isArray(source.fields) ? source.fields : [],
      options: Array.isArray(source.options) ? source.options : [],
    };
  }

  if (uiAction && typeof uiAction === 'object') {
    const source = uiAction as Record<string, unknown>;
    return {
      kind:
        typeof source.kind === 'string' && source.kind.trim().length > 0
          ? source.kind
          : 'form',
      submit_label: inferLegacySubmitLabel(uiAction),
      fields: [],
      options: [],
    };
  }

  return {
    kind: 'form',
    submit_label: 'Validate & Continue',
    fields: [],
    options: [],
  };
}

function inferLegacySubmitLabel(uiAction: unknown): string {
  if (!uiAction || typeof uiAction !== 'object') {
    return 'Validate & Continue';
  }
  const source = uiAction as Record<string, unknown>;
  const label = typeof source.label === 'string' ? source.label.trim() : '';
  return label.length > 0 ? label : 'Validate & Continue';
}
