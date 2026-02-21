import { useEffect, useMemo, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { TemplateDefinition } from '../types/definition';
import type { UISchema } from '../types/uiSchema';
import { buildZodSchema } from '../utils/zodSchemaBuilder';

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((entry) => canonicalize(entry));
  }

  if (value && typeof value === 'object') {
    const normalized: Record<string, unknown> = {};
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) =>
      left.localeCompare(right),
    );

    for (const [key, entry] of entries) {
      normalized[key] = canonicalize(entry);
    }

    return normalized;
  }

  return value;
}

function stableSerialize(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

/**
 * Sets up React Hook Form with a Zod schema derived from the
 * DefinitionNode tree and UISchema.
 *
 * Re-initialises the form whenever the definition or initial data changes
 * (e.g. when the user switches templates in the public sandbox).
 */
export function useSubmodelForm(
  definition?: TemplateDefinition,
  uiSchema?: UISchema,
  initialData?: Record<string, unknown>,
) {
  const zodSchema = useMemo(
    () => buildZodSchema(definition, uiSchema),
    [definition, uiSchema],
  );

  const form = useForm<Record<string, unknown>>({
    resolver: zodResolver(zodSchema),
    defaultValues: initialData ?? {},
    mode: 'onChange',
  });
  const reset = form.reset;
  const initialValues = useMemo(() => initialData ?? {}, [initialData]);
  const definitionSignature = useMemo(
    () => stableSerialize(definition ?? null),
    [definition],
  );
  const initialDataSignature = useMemo(
    () => stableSerialize(initialValues),
    [initialValues],
  );
  const lastResetSignatureRef = useRef<string | null>(null);

  // Reset the form when the backing definition or data changes so that
  // switching templates does not leave stale values from a prior form.
  useEffect(() => {
    const resetSignature = `${definitionSignature}|${initialDataSignature}`;
    if (lastResetSignatureRef.current === resetSignature) return;
    lastResetSignatureRef.current = resetSignature;
    reset(initialValues);
  }, [definitionSignature, initialDataSignature, initialValues, reset]);

  return { form, zodSchema };
}
