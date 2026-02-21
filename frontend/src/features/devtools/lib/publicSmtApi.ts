import { apiFetch, getApiErrorMessage } from '@/lib/api';
import type { TemplateContractResponse } from '@/features/editor/types/definition';
import {
  extractPublicSmtRateLimit,
  parsePublicSmtApiError,
  type PublicSmtRateLimitMeta,
} from './publicSmtErrors';

export type PublicTemplateStatus = 'published' | 'deprecated' | 'all';

export type PublicTemplateSummary = {
  template_key: string;
  display_name: string;
  catalog_status: string;
  catalog_folder?: string | null;
  semantic_id: string;
  latest_version: string;
  fetched_at: string;
  source_metadata: {
    resolved_version: string;
    source_repo_ref: string;
    source_file_path?: string | null;
    source_file_sha?: string | null;
    source_kind?: string | null;
    selection_strategy?: string | null;
    source_url: string;
    catalog_status?: string | null;
    catalog_folder?: string | null;
    display_name?: string | null;
  };
};

export type PublicTemplateListResponse = {
  templates: PublicTemplateSummary[];
  count: number;
  status_filter: PublicTemplateStatus;
  search?: string | null;
};

export type PublicTemplateDetailResponse = {
  template_key: string;
  display_name: string;
  catalog_status: string;
  catalog_folder?: string | null;
  semantic_id: string;
  latest_version: string;
  fetched_at: string;
  source_metadata: PublicTemplateSummary['source_metadata'];
  versions: PublicTemplateVersion[];
};

export type PublicTemplateVersion = {
  version: string;
  resolved_version: string;
  status: string;
  source_repo_ref?: string | null;
  source_file_sha?: string | null;
  is_default: boolean;
  fetched_at?: string | null;
};

export type PublicTemplateVersionsResponse = {
  template_key: string;
  versions: PublicTemplateVersion[];
  count: number;
};

export type PublicPreviewResponse = {
  template_key: string;
  version: string;
  aas_environment: Record<string, unknown>;
  warnings: string[];
};

export type PublicPreviewRequest = {
  template_key: string;
  version?: string;
  data: Record<string, unknown>;
};

export type PublicExportFormat = 'json' | 'aasx' | 'pdf';

export type PublicExportRequest = PublicPreviewRequest & {
  format: PublicExportFormat;
};

export type PublicExportResult = {
  blob: Blob;
  contentType: string;
  filename: string;
};

export type PublicPreviewWithMetaResponse = {
  data: PublicPreviewResponse;
  meta: PublicSmtRateLimitMeta;
};

export type PublicExportWithMetaResult = {
  result: PublicExportResult;
  meta: PublicSmtRateLimitMeta;
};

function resolveFilenameFromDisposition(
  contentDisposition: string | null,
  fallback: string,
): string {
  if (!contentDisposition) return fallback;
  const match = /filename="([^"]+)"/i.exec(contentDisposition);
  if (!match) return fallback;
  return match[1] || fallback;
}

export async function listPublicTemplates(params: {
  status?: PublicTemplateStatus;
  search?: string;
} = {}): Promise<PublicTemplateListResponse> {
  const query = new URLSearchParams();
  query.set('status', params.status ?? 'published');
  if (params.search && params.search.trim()) {
    query.set('search', params.search.trim());
  }
  const response = await apiFetch(`/api/v1/public/smt/templates?${query.toString()}`);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load public templates'));
  }
  return response.json() as Promise<PublicTemplateListResponse>;
}

export async function getPublicTemplate(templateKey: string): Promise<PublicTemplateDetailResponse> {
  const response = await apiFetch(`/api/v1/public/smt/templates/${encodeURIComponent(templateKey)}`);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load template metadata'));
  }
  return response.json() as Promise<PublicTemplateDetailResponse>;
}

export async function listPublicTemplateVersions(
  templateKey: string,
): Promise<PublicTemplateVersionsResponse> {
  const response = await apiFetch(
    `/api/v1/public/smt/templates/${encodeURIComponent(templateKey)}/versions`,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load template versions'));
  }
  return response.json() as Promise<PublicTemplateVersionsResponse>;
}

export async function getPublicTemplateContract(
  templateKey: string,
  version?: string,
): Promise<TemplateContractResponse> {
  const query = version ? `?version=${encodeURIComponent(version)}` : '';
  const response = await apiFetch(
    `/api/v1/public/smt/templates/${encodeURIComponent(templateKey)}/contract${query}`,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to load template contract'));
  }
  return response.json() as Promise<TemplateContractResponse>;
}

export async function previewPublicTemplate(
  payload: PublicPreviewRequest,
): Promise<PublicPreviewResponse> {
  const responseWithMeta = await previewPublicTemplateWithMeta(payload);
  return responseWithMeta.data;
}

export async function previewPublicTemplateWithMeta(
  payload: PublicPreviewRequest,
): Promise<PublicPreviewWithMetaResponse> {
  const response = await apiFetch('/api/v1/public/smt/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parsePublicSmtApiError(response, 'Failed to generate AAS preview');
  }
  return {
    data: (await response.json()) as PublicPreviewResponse,
    meta: extractPublicSmtRateLimit(response.headers),
  };
}

export async function exportPublicTemplate(
  payload: PublicExportRequest,
): Promise<PublicExportResult> {
  const responseWithMeta = await exportPublicTemplateWithMeta(payload);
  return responseWithMeta.result;
}

export async function exportPublicTemplateWithMeta(
  payload: PublicExportRequest,
): Promise<PublicExportWithMetaResult> {
  const response = await apiFetch('/api/v1/public/smt/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await parsePublicSmtApiError(
      response,
      `Failed to export ${payload.format.toUpperCase()}`,
    );
  }
  const blob = await response.blob();
  const filename = resolveFilenameFromDisposition(
    response.headers.get('content-disposition'),
    `${payload.template_key}.${payload.format}`,
  );
  return {
    result: {
      blob,
      filename,
      contentType: response.headers.get('content-type') ?? 'application/octet-stream',
    },
    meta: extractPublicSmtRateLimit(response.headers),
  };
}
