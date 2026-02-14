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
  const parsed = cirpassLabManifestSchema.safeParse(input);
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
