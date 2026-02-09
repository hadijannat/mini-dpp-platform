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
export type TemplateResponse = components['schemas']['TemplateResponse'];
export type TemplateListResponse = components['schemas']['TemplateListResponse'];
