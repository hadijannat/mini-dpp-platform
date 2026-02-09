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
