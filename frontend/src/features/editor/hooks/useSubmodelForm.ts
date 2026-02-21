import { useEffect, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { TemplateDefinition } from '../types/definition';
import type { UISchema } from '../types/uiSchema';
import { buildZodSchema } from '../utils/zodSchemaBuilder';

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

  // Reset the form when the backing definition or data changes so that
  // switching templates does not leave stale values from a prior form.
  useEffect(() => {
    form.reset(initialData ?? {});
  }, [definition, initialData, form]);

  return { form, zodSchema };
}
