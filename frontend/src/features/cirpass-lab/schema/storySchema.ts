import { z } from 'zod';

export const cirpassLevelKeySchema = z.enum([
  'create',
  'access',
  'update',
  'transfer',
  'deactivate',
]);

export const cirpassLabModeSchema = z.enum(['mock', 'live']);

export const cirpassLabVariantSchema = z.enum(['happy', 'unauthorized', 'not_found']);

export const cirpassPersonaSchema = z.enum([
  'Manufacturer',
  'Supplier',
  'Retailer',
  'Consumer',
  'Repairer',
  'Recycler',
  'Authority',
]);

export const cirpassStepCheckSchema = z.object({
  type: z.enum(['jsonpath', 'jmespath', 'status', 'schema']),
  expression: z.string().trim().min(1).optional(),
  expected: z.unknown().optional(),
});

export const cirpassApiCallSchema = z.object({
  method: z.enum(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']),
  path: z.string().trim().min(1),
  auth: z.enum(['none', 'user', 'service']).default('none'),
  request_example: z.record(z.unknown()).optional(),
  expected_status: z.number().int().min(100).max(599).optional(),
  response_example: z.record(z.unknown()).optional(),
});

export const cirpassUiActionSchema = z.object({
  label: z.string().trim().min(1),
  kind: z.enum(['click', 'form', 'scan', 'select']),
});

export const cirpassInteractionValidationSchema = z.object({
  min_length: z.number().int().min(0).optional(),
  max_length: z.number().int().min(0).optional(),
  gt: z.number().optional(),
  gte: z.number().optional(),
  lt: z.number().optional(),
  lte: z.number().optional(),
  pattern: z.string().trim().min(1).optional(),
  equals: z.union([z.string(), z.number(), z.boolean()]).optional(),
});

export const cirpassInteractionOptionSchema = z.object({
  label: z.string().trim().min(1),
  value: z.string().trim().min(1),
});

export const cirpassInteractionFieldSchema = z.object({
  name: z.string().trim().min(1),
  label: z.string().trim().min(1),
  type: z.enum(['text', 'textarea', 'number', 'checkbox', 'select']),
  placeholder: z.string().trim().optional(),
  required: z.boolean().default(false),
  hint: z.string().trim().optional(),
  validation: cirpassInteractionValidationSchema.optional(),
  options: z.array(cirpassInteractionOptionSchema).optional(),
  test_id: z.string().trim().min(1).optional(),
});

export const cirpassStepInteractionSchema = z.object({
  kind: z.enum(['click', 'form', 'scan', 'select']).default('form'),
  submit_label: z.string().trim().min(1).default('Validate & Continue'),
  hint_text: z.string().trim().min(1).optional(),
  success_message: z.string().trim().min(1).optional(),
  failure_message: z.string().trim().min(1).optional(),
  fields: z.array(cirpassInteractionFieldSchema).default([]),
  options: z.array(cirpassInteractionOptionSchema).optional(),
});

export const cirpassArtifactsSchema = z.object({
  before: z.record(z.unknown()).optional(),
  after: z.record(z.unknown()).optional(),
  diff_hint: z.string().trim().min(1).optional(),
});

export const cirpassPolicyInspectorSchema = z.object({
  required_role: z.string().trim().min(1).optional(),
  opa_policy: z.string().trim().min(1).optional(),
  expected_decision: z.enum(['allow', 'deny', 'mask']).optional(),
  note: z.string().trim().min(1).optional(),
});

export const cirpassReferenceSchema = z.object({
  label: z.string().trim().min(1),
  ref: z.string().trim().url(),
});

export const cirpassStepSchema = z.object({
  id: z.string().trim().min(1),
  level: cirpassLevelKeySchema,
  title: z.string().trim().min(1),
  actor: z.string().trim().min(1),
  intent: z.string().trim().min(1),
  explanation_md: z.string().trim().min(1),
  ui_action: cirpassUiActionSchema.optional(),
  interaction: cirpassStepInteractionSchema.optional(),
  actor_goal: z.string().trim().min(1).optional(),
  physical_story_md: z.string().trim().min(1).optional(),
  why_it_matters_md: z.string().trim().min(1).optional(),
  api: cirpassApiCallSchema.optional(),
  artifacts: cirpassArtifactsSchema.optional(),
  checks: z.array(cirpassStepCheckSchema).default([]),
  policy: cirpassPolicyInspectorSchema.optional(),
  variants: z.array(cirpassLabVariantSchema).min(1).default(['happy']),
});

export const cirpassStorySchema = z.object({
  id: z.string().trim().min(1),
  title: z.string().trim().min(1),
  summary: z.string().trim().min(1),
  personas: z.array(cirpassPersonaSchema.or(z.string().trim().min(1))).min(1),
  learning_goals: z.array(z.string().trim().min(1)).default([]),
  preconditions_md: z.string().trim().min(1).optional(),
  steps: z.array(cirpassStepSchema).min(1),
  references: z.array(cirpassReferenceSchema).default([]),
  version: z.string().trim().min(1).optional(),
  last_reviewed: z.string().trim().min(1).optional(),
});

export const cirpassLabManifestSchema = z.object({
  manifest_version: z.string().trim().min(1),
  story_version: z.string().trim().min(1),
  generated_at: z.string().trim().min(1),
  source_status: z.enum(['fresh', 'fallback']),
  stories: z.array(cirpassStorySchema).min(1),
  feature_flags: z.object({
    scenario_engine_enabled: z.boolean(),
    live_mode_enabled: z.boolean(),
    inspector_enabled: z.boolean(),
  }),
});

export type CirpassLabMode = z.infer<typeof cirpassLabModeSchema>;
export type CirpassLabVariant = z.infer<typeof cirpassLabVariantSchema>;
export type CirpassLevelKey = z.infer<typeof cirpassLevelKeySchema>;
export type CirpassLabManifest = z.infer<typeof cirpassLabManifestSchema>;
export type CirpassLabStory = z.infer<typeof cirpassStorySchema>;
export type CirpassLabStep = z.infer<typeof cirpassStepSchema>;
export type CirpassLabStepInteraction = z.infer<typeof cirpassStepInteractionSchema>;
