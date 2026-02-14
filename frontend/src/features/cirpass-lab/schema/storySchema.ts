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
