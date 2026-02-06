import { useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { TemplateDefinition } from '../types/definition';
import type { UISchema } from '../types/uiSchema';
import { buildZodSchema } from '../utils/zodSchemaBuilder';

/**
 * Sets up React Hook Form with a Zod schema derived from the
 * DefinitionNode tree and UISchema.
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

  return { form, zodSchema };
}
