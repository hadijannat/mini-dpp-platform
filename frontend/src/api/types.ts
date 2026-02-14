/**
 * Named type aliases re-exported from the generated OpenAPI schema.
 * Import these instead of using `any` in page components.
 */
import type { components } from './schema';

// DPP types
export type DPPResponse = components['schemas']['DPPResponse'];
export type DPPListResponse = components['schemas']['DPPListResponse'];
export type DPPDetailResponse = components['schemas']['DPPDetailResponse'];
export type PublicDPPResponse = components['schemas']['PublicDPPResponse'];
export type CreateDPPRequest = components['schemas']['CreateDPPRequest'];

// Template types
type OpenApiTemplateResponse = components['schemas']['TemplateResponse'];
type OpenApiTemplateListResponse = components['schemas']['TemplateListResponse'];

export type TemplateSupportStatus = 'supported' | 'experimental' | 'unavailable';

export type TemplateResponse = OpenApiTemplateResponse & {
  support_status?: TemplateSupportStatus;
  refresh_enabled?: boolean;
};

export type TemplateListResponse = OpenApiTemplateListResponse & {
  templates: TemplateResponse[];
  attempted_count?: number | null;
  successful_count?: number | null;
  failed_count?: number | null;
  skipped_count?: number | null;
};

export interface LandingSummary {
  tenant_slug: string;
  published_dpps: number;
  active_product_families: number;
  dpps_with_traceability: number;
  latest_publish_at: string | null;
  generated_at: string | null;
  scope?: string | null;
  refresh_sla_seconds?: number | null;
}

export type RegulatoryTimelineTrack = 'regulation' | 'standards';
export type RegulatoryTimelineTrackFilter = 'all' | RegulatoryTimelineTrack;
export type RegulatoryTimelineSourceStatus = 'fresh' | 'stale';
export type RegulatoryTimelineEventStatus = 'past' | 'today' | 'upcoming';
export type RegulatoryTimelineDatePrecision = 'day' | 'month';
export type RegulatoryTimelineVerificationMethod = 'source-hash' | 'content-match' | 'manual';
export type RegulatoryTimelineConfidence = 'high' | 'medium' | 'low';

export interface RegulatoryTimelineSource {
  label: string;
  url: string;
  publisher: string;
  retrieved_at: string;
  sha256?: string | null;
}

export interface RegulatoryTimelineVerification {
  checked_at: string;
  method: RegulatoryTimelineVerificationMethod;
  confidence: RegulatoryTimelineConfidence;
}

export interface RegulatoryTimelineEvent {
  id: string;
  date: string;
  date_precision: RegulatoryTimelineDatePrecision;
  track: RegulatoryTimelineTrack;
  title: string;
  plain_summary: string;
  audience_tags: string[];
  status: RegulatoryTimelineEventStatus;
  verified: boolean;
  verification: RegulatoryTimelineVerification;
  sources: RegulatoryTimelineSource[];
}

export interface RegulatoryTimelineResponse {
  generated_at: string;
  fetched_at: string;
  source_status: RegulatoryTimelineSourceStatus;
  refresh_sla_seconds: number;
  digest_sha256: string;
  events: RegulatoryTimelineEvent[];
}

export type CirpassLevelKey = 'create' | 'access' | 'update' | 'transfer' | 'deactivate';
export type CirpassLabMode = 'mock' | 'live';
export type CirpassLabVariant = 'happy' | 'unauthorized' | 'not_found';
export type CirpassLabTelemetryEventType =
  | 'step_view'
  | 'step_submit'
  | 'hint'
  | 'mode_switch'
  | 'reset_story'
  | 'reset_all';
export type CirpassLabTelemetryResult = 'success' | 'error' | 'info';

export interface CirpassStory {
  id: string;
  title: string;
  summary: string;
  technical_note?: string | null;
}

export interface CirpassLevel {
  level: CirpassLevelKey;
  label: string;
  objective: string;
  stories: CirpassStory[];
}

export interface CirpassStoryFeed {
  version: string;
  release_date: string | null;
  source_url: string;
  zenodo_record_url: string;
  source_status: 'fresh' | 'stale';
  generated_at: string;
  fetched_at: string;
  levels: CirpassLevel[];
}

export interface CirpassSession {
  session_token: string;
  expires_at: string;
}

export interface CirpassLeaderboardEntry {
  rank: number;
  nickname: string;
  score: number;
  completion_seconds: number;
  version: string;
  created_at: string;
}

export interface CirpassLeaderboard {
  version: string;
  entries: CirpassLeaderboardEntry[];
}

export interface CirpassLeaderboardSubmitRequest {
  session_token: string;
  nickname: string;
  score: number;
  completion_seconds: number;
  version: string;
}

export interface CirpassLeaderboardSubmitResponse {
  accepted: boolean;
  rank: number | null;
  best_score: number | null;
  version: string;
}

export interface CirpassLabReference {
  label: string;
  ref: string;
}

export interface CirpassLabUiAction {
  label: string;
  kind: 'click' | 'form' | 'scan' | 'select';
}

export interface CirpassLabInteractionValidation {
  min_length?: number | null;
  max_length?: number | null;
  gt?: number | null;
  gte?: number | null;
  lt?: number | null;
  lte?: number | null;
  pattern?: string | null;
  equals?: string | number | boolean | null;
}

export interface CirpassLabInteractionOption {
  label: string;
  value: string;
}

export interface CirpassLabInteractionField {
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'number' | 'checkbox' | 'select';
  placeholder?: string | null;
  required?: boolean;
  hint?: string | null;
  validation?: CirpassLabInteractionValidation | null;
  options?: CirpassLabInteractionOption[];
  test_id?: string | null;
}

export interface CirpassLabStepInteraction {
  kind: 'click' | 'form' | 'scan' | 'select';
  submit_label?: string;
  hint_text?: string | null;
  success_message?: string | null;
  failure_message?: string | null;
  fields?: CirpassLabInteractionField[];
  options?: CirpassLabInteractionOption[];
}

export interface CirpassLabApiCall {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  path: string;
  auth: 'none' | 'user' | 'service';
  request_example?: Record<string, unknown> | null;
  expected_status?: number | null;
  response_example?: Record<string, unknown> | null;
}

export interface CirpassLabStepCheck {
  type: 'jsonpath' | 'jmespath' | 'status' | 'schema';
  expression?: string | null;
  expected?: unknown;
}

export interface CirpassLabArtifacts {
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  diff_hint?: string | null;
}

export interface CirpassLabPolicyInspector {
  required_role?: string | null;
  opa_policy?: string | null;
  expected_decision?: 'allow' | 'deny' | 'mask' | null;
  note?: string | null;
}

export interface CirpassLabStep {
  id: string;
  level: CirpassLevelKey;
  title: string;
  actor: string;
  intent: string;
  explanation_md: string;
  ui_action?: CirpassLabUiAction | null;
  interaction?: CirpassLabStepInteraction | null;
  actor_goal?: string | null;
  physical_story_md?: string | null;
  why_it_matters_md?: string | null;
  api?: CirpassLabApiCall | null;
  artifacts?: CirpassLabArtifacts | null;
  checks: CirpassLabStepCheck[];
  policy?: CirpassLabPolicyInspector | null;
  variants: CirpassLabVariant[];
}

export interface CirpassLabStory {
  id: string;
  title: string;
  summary: string;
  personas: string[];
  learning_goals: string[];
  preconditions_md?: string | null;
  references: CirpassLabReference[];
  version?: string | null;
  last_reviewed?: string | null;
  steps: CirpassLabStep[];
}

export interface CirpassLabFeatureFlags {
  scenario_engine_enabled: boolean;
  live_mode_enabled: boolean;
  inspector_enabled: boolean;
}

export interface CirpassLabManifest {
  manifest_version: string;
  story_version: string;
  generated_at: string;
  source_status: 'fresh' | 'fallback';
  stories: CirpassLabStory[];
  feature_flags: CirpassLabFeatureFlags;
}

export interface CirpassLabEventRequest {
  session_token: string;
  story_id: string;
  step_id: string;
  event_type: CirpassLabTelemetryEventType;
  mode: CirpassLabMode;
  variant: CirpassLabVariant;
  result: CirpassLabTelemetryResult;
  latency_ms?: number;
  metadata?: Record<string, unknown>;
}

export interface CirpassLabEventResponse {
  accepted: boolean;
  event_id: string;
  stored_at: string;
}

// Data carrier types
export type DataCarrierCreateRequest = components['schemas']['DataCarrierCreateRequest'];
export type DataCarrierUpdateRequest = components['schemas']['DataCarrierUpdateRequest'];
export type DataCarrierRenderRequest = components['schemas']['DataCarrierRenderRequest'];
export type DataCarrierDeprecateRequest = components['schemas']['DataCarrierDeprecateRequest'];
export type DataCarrierWithdrawRequest = components['schemas']['DataCarrierWithdrawRequest'];
export type DataCarrierReissueRequest = components['schemas']['DataCarrierReissueRequest'];

export type DataCarrierResponse = components['schemas']['DataCarrierResponse'];
export type DataCarrierListResponse = components['schemas']['DataCarrierListResponse'];
export type DataCarrierPreSalePackResponse = components['schemas']['DataCarrierPreSalePackResponse'];
export type DataCarrierRegistryExportResponse =
  components['schemas']['DataCarrierRegistryExportResponse'];
