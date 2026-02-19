import { tenantApiFetch, getApiErrorMessage } from '@/lib/api';

// ---------------------------------------------------------------------------
// Feature flag error
// ---------------------------------------------------------------------------

export class FeatureDisabledError extends Error {
  constructor() {
    super('OPC UA integration is not enabled');
    this.name = 'FeatureDisabledError';
  }
}

// ---------------------------------------------------------------------------
// Enums (const objects matching backend Python enums)
// ---------------------------------------------------------------------------

export const OPCUAAuthType = {
  ANONYMOUS: 'anonymous',
  USERNAME_PASSWORD: 'username_password',
  CERTIFICATE: 'certificate',
} as const;

export type OPCUAAuthType = (typeof OPCUAAuthType)[keyof typeof OPCUAAuthType];

export const OPCUAConnectionStatus = {
  DISABLED: 'disabled',
  HEALTHY: 'healthy',
  DEGRADED: 'degraded',
  ERROR: 'error',
} as const;

export type OPCUAConnectionStatus =
  (typeof OPCUAConnectionStatus)[keyof typeof OPCUAConnectionStatus];

// ---------------------------------------------------------------------------
// Response types (snake_case — matching backend JSON serialization)
// ---------------------------------------------------------------------------

export interface OPCUASourceResponse {
  id: string;
  tenant_id: string;
  name: string;
  endpoint_url: string;
  security_policy: string | null;
  security_mode: string | null;
  auth_type: OPCUAAuthType;
  username: string | null;
  has_password: boolean;
  client_cert_ref: string | null;
  client_key_ref: string | null;
  server_cert_pinned_sha256: string | null;
  connection_status: OPCUAConnectionStatus;
  last_seen_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface OPCUASourceListResponse {
  items: OPCUASourceResponse[];
  total: number;
}

export interface TestConnectionResult {
  success: boolean;
  serverInfo: Record<string, unknown> | null;
  error: string | null;
  latencyMs: number | null;
}

export interface DigitalLinkResponse {
  digital_link_uri: string;
  gtin: string;
  serial_number: string | null;
  is_pseudo_gtin: boolean;
}

// ---------------------------------------------------------------------------
// Request/create types (camelCase — frontend convention)
// ---------------------------------------------------------------------------

export interface OPCUASourceCreateInput {
  name: string;
  endpointUrl: string;
  securityPolicy?: string | null;
  securityMode?: string | null;
  authType?: OPCUAAuthType;
  username?: string | null;
  password?: string | null;
  clientCertRef?: string | null;
  clientKeyRef?: string | null;
  serverCertPinnedSha256?: string | null;
}

export interface OPCUASourceUpdateInput {
  name?: string;
  endpointUrl?: string;
  securityPolicy?: string | null;
  securityMode?: string | null;
  authType?: OPCUAAuthType;
  username?: string | null;
  password?: string | null;
  clientCertRef?: string | null;
  clientKeyRef?: string | null;
  serverCertPinnedSha256?: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function checkFeatureEnabled(res: Response): void {
  if (res.status === 410) throw new FeatureDisabledError();
}

// ---------------------------------------------------------------------------
// Source API functions
// ---------------------------------------------------------------------------

export async function fetchSources(
  token: string,
  params?: { offset?: number; limit?: number },
): Promise<OPCUASourceListResponse> {
  const query = new URLSearchParams();
  if (params?.offset != null) query.set('offset', String(params.offset));
  if (params?.limit != null) query.set('limit', String(params.limit));
  const qs = query.toString();

  const res = await tenantApiFetch(`/opcua/sources${qs ? `?${qs}` : ''}`, {}, token);
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to list OPC UA sources'));
  return res.json() as Promise<OPCUASourceListResponse>;
}

export async function fetchSource(
  token: string,
  sourceId: string,
): Promise<OPCUASourceResponse> {
  const res = await tenantApiFetch(
    `/opcua/sources/${encodeURIComponent(sourceId)}`,
    {},
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to fetch OPC UA source'));
  return res.json() as Promise<OPCUASourceResponse>;
}

export async function createSource(
  token: string,
  data: OPCUASourceCreateInput,
): Promise<OPCUASourceResponse> {
  const res = await tenantApiFetch(
    '/opcua/sources',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to create OPC UA source'));
  return res.json() as Promise<OPCUASourceResponse>;
}

export async function updateSource(
  token: string,
  sourceId: string,
  data: OPCUASourceUpdateInput,
): Promise<OPCUASourceResponse> {
  const res = await tenantApiFetch(
    `/opcua/sources/${encodeURIComponent(sourceId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to update OPC UA source'));
  return res.json() as Promise<OPCUASourceResponse>;
}

export async function deleteSource(
  token: string,
  sourceId: string,
): Promise<void> {
  const res = await tenantApiFetch(
    `/opcua/sources/${encodeURIComponent(sourceId)}`,
    { method: 'DELETE' },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to delete OPC UA source'));
}

export async function testSourceConnection(
  token: string,
  sourceId: string,
): Promise<TestConnectionResult> {
  const res = await tenantApiFetch(
    `/opcua/sources/${encodeURIComponent(sourceId)}/test-connection`,
    { method: 'POST' },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to test OPC UA connection'));
  return res.json() as Promise<TestConnectionResult>;
}

// ---------------------------------------------------------------------------
// Digital Link (on DPP router, not OPC UA prefix)
// ---------------------------------------------------------------------------

export async function fetchDigitalLink(
  token: string,
  dppId: string,
): Promise<DigitalLinkResponse> {
  const res = await tenantApiFetch(
    `/dpps/${encodeURIComponent(dppId)}/digital-link`,
    {},
    token,
  );
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to fetch digital link'));
  return res.json() as Promise<DigitalLinkResponse>;
}
