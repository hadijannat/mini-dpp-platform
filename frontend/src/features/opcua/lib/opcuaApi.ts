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

export interface OPCUAFeatureStatusResponse {
  enabled: boolean;
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

export async function fetchOpcuaFeatureStatus(token: string): Promise<OPCUAFeatureStatusResponse> {
  const res = await tenantApiFetch('/opcua/status', {}, token);
  if (!res.ok) {
    throw new Error(await getApiErrorMessage(res, 'Failed to load OPC UA feature status'));
  }
  return res.json() as Promise<OPCUAFeatureStatusResponse>;
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

// ---------------------------------------------------------------------------
// NodeSet response types
// ---------------------------------------------------------------------------

export interface OPCUANodeSetResponse {
  id: string;
  tenant_id: string;
  source_id: string | null;
  namespace_uri: string;
  nodeset_version: string | null;
  publication_date: string | null;
  companion_spec_name: string | null;
  companion_spec_version: string | null;
  nodeset_file_ref: string;
  companion_spec_file_ref: string | null;
  hash_sha256: string;
  parsed_summary_json: Record<string, unknown>;
  node_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface OPCUANodeSetDetailResponse extends OPCUANodeSetResponse {
  parsed_node_graph: Record<string, unknown>;
}

export interface OPCUANodeSetListResponse {
  items: OPCUANodeSetResponse[];
  total: number;
}

export interface NodeSearchResult {
  nodeId: string;
  browseName: string;
  nodeClass: string;
  dataType: string | null;
  description: string | null;
  engineeringUnit: string | null;
  parentNodeId: string | null;
}

// ---------------------------------------------------------------------------
// Mapping enums
// ---------------------------------------------------------------------------

export const OPCUAMappingType = {
  AAS_PATCH: 'aas_patch',
  EPCIS_EVENT: 'epcis_event',
} as const;
export type OPCUAMappingType = (typeof OPCUAMappingType)[keyof typeof OPCUAMappingType];

export const DPPBindingMode = {
  BY_DPP_ID: 'by_dpp_id',
  BY_ASSET_ID_QUERY: 'by_asset_id_query',
} as const;
export type DPPBindingMode = (typeof DPPBindingMode)[keyof typeof DPPBindingMode];

// ---------------------------------------------------------------------------
// Mapping response types
// ---------------------------------------------------------------------------

export interface OPCUAMappingResponse {
  id: string;
  tenant_id: string;
  source_id: string;
  nodeset_id: string | null;
  mapping_type: OPCUAMappingType;
  opcua_node_id: string;
  opcua_browse_path: string | null;
  opcua_datatype: string | null;
  sampling_interval_ms: number | null;
  dpp_binding_mode: DPPBindingMode;
  dpp_id: string | null;
  asset_id_query: Record<string, unknown> | null;
  target_template_key: string | null;
  target_submodel_id: string | null;
  target_aas_path: string | null;
  patch_op: string | null;
  value_transform_expr: string | null;
  unit_hint: string | null;
  samm_aspect_urn: string | null;
  samm_property: string | null;
  samm_version: string | null;
  epcis_event_type: string | null;
  epcis_biz_step: string | null;
  epcis_disposition: string | null;
  epcis_action: string | null;
  epcis_read_point: string | null;
  epcis_biz_location: string | null;
  epcis_source_event_id_template: string | null;
  is_enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface OPCUAMappingListResponse {
  items: OPCUAMappingResponse[];
  total: number;
}

// ---------------------------------------------------------------------------
// Mapping request/create types
// ---------------------------------------------------------------------------

export interface OPCUAMappingCreateInput {
  sourceId: string;
  nodesetId?: string | null;
  mappingType: OPCUAMappingType;
  opcuaNodeId: string;
  opcuaBrowsePath?: string | null;
  opcuaDatatype?: string | null;
  samplingIntervalMs?: number | null;
  dppBindingMode?: DPPBindingMode;
  dppId?: string | null;
  assetIdQuery?: Record<string, unknown> | null;
  targetTemplateKey?: string | null;
  targetSubmodelId?: string | null;
  targetAasPath?: string | null;
  patchOp?: string | null;
  valueTransformExpr?: string | null;
  unitHint?: string | null;
  sammAspectUrn?: string | null;
  sammProperty?: string | null;
  sammVersion?: string | null;
  epcisEventType?: string | null;
  epcisBizStep?: string | null;
  epcisDisposition?: string | null;
  epcisAction?: string | null;
  epcisReadPoint?: string | null;
  epcisBizLocation?: string | null;
  epcisSourceEventIdTemplate?: string | null;
  isEnabled?: boolean;
}

export interface OPCUAMappingUpdateInput extends Partial<Omit<OPCUAMappingCreateInput, 'sourceId'>> {}

export interface MappingValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

export interface DryRunDiffEntry {
  op: string;
  path: string;
  oldValue: unknown;
  newValue: unknown;
}

export interface MappingDryRunResult {
  mappingId: string;
  dppId: string | null;
  diff: DryRunDiffEntry[];
  appliedValue: unknown;
  transformOutput: unknown;
}

// ---------------------------------------------------------------------------
// Dataspace enums
// ---------------------------------------------------------------------------

export const DataspaceJobStatus = {
  QUEUED: 'queued',
  IN_PROGRESS: 'in_progress',
  SUCCEEDED: 'succeeded',
  FAILED: 'failed',
} as const;
export type DataspaceJobStatus = (typeof DataspaceJobStatus)[keyof typeof DataspaceJobStatus];

// ---------------------------------------------------------------------------
// Dataspace response types
// ---------------------------------------------------------------------------

export interface DataspacePublicationJobResponse {
  id: string;
  tenant_id: string;
  dpp_id: string;
  status: DataspaceJobStatus;
  target: string;
  artifact_refs: Record<string, unknown>;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataspacePublicationJobListResponse {
  items: DataspacePublicationJobResponse[];
  total: number;
}

// ---------------------------------------------------------------------------
// Dataspace request types
// ---------------------------------------------------------------------------

export interface DataspacePublishInput {
  dppId: string;
  target?: string;
}

// ---------------------------------------------------------------------------
// NodeSet API functions
// ---------------------------------------------------------------------------

export async function fetchNodesets(
  token: string,
  params?: { sourceId?: string; offset?: number; limit?: number },
): Promise<OPCUANodeSetListResponse> {
  const query = new URLSearchParams();
  if (params?.sourceId != null) query.set('sourceId', params.sourceId);
  if (params?.offset != null) query.set('offset', String(params.offset));
  if (params?.limit != null) query.set('limit', String(params.limit));
  const qs = query.toString();

  const res = await tenantApiFetch(`/opcua/nodesets${qs ? `?${qs}` : ''}`, {}, token);
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to list OPC UA nodesets'));
  return res.json() as Promise<OPCUANodeSetListResponse>;
}

export async function uploadNodeset(
  token: string,
  file: File,
  params?: { sourceId?: string; companionSpecName?: string; companionSpecVersion?: string },
): Promise<OPCUANodeSetResponse> {
  const query = new URLSearchParams();
  if (params?.sourceId != null) query.set('sourceId', params.sourceId);
  if (params?.companionSpecName != null) query.set('companionSpecName', params.companionSpecName);
  if (params?.companionSpecVersion != null)
    query.set('companionSpecVersion', params.companionSpecVersion);
  const qs = query.toString();

  const formData = new FormData();
  formData.append('xml_file', file);

  const res = await tenantApiFetch(
    `/opcua/nodesets/upload${qs ? `?${qs}` : ''}`,
    {
      method: 'POST',
      body: formData,
    },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to upload OPC UA nodeset'));
  return res.json() as Promise<OPCUANodeSetResponse>;
}

export async function fetchNodeset(
  token: string,
  nodesetId: string,
): Promise<OPCUANodeSetDetailResponse> {
  const res = await tenantApiFetch(
    `/opcua/nodesets/${encodeURIComponent(nodesetId)}`,
    {},
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to fetch OPC UA nodeset'));
  return res.json() as Promise<OPCUANodeSetDetailResponse>;
}

export async function downloadNodeset(
  token: string,
  nodesetId: string,
): Promise<{ download_url: string }> {
  const res = await tenantApiFetch(
    `/opcua/nodesets/${encodeURIComponent(nodesetId)}/download`,
    {},
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to get OPC UA nodeset download URL'));
  return res.json() as Promise<{ download_url: string }>;
}

export async function searchNodesetNodes(
  token: string,
  nodesetId: string,
  params: { q: string; nodeClass?: string; limit?: number },
): Promise<NodeSearchResult[]> {
  const query = new URLSearchParams();
  query.set('q', params.q);
  if (params.nodeClass != null) query.set('nodeClass', params.nodeClass);
  if (params.limit != null) query.set('limit', String(params.limit));
  const qs = query.toString();

  const res = await tenantApiFetch(
    `/opcua/nodesets/${encodeURIComponent(nodesetId)}/nodes${qs ? `?${qs}` : ''}`,
    {},
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to search OPC UA nodeset nodes'));
  return res.json() as Promise<NodeSearchResult[]>;
}

export async function deleteNodeset(
  token: string,
  nodesetId: string,
): Promise<void> {
  const res = await tenantApiFetch(
    `/opcua/nodesets/${encodeURIComponent(nodesetId)}`,
    { method: 'DELETE' },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to delete OPC UA nodeset'));
}

// ---------------------------------------------------------------------------
// Mapping API functions
// ---------------------------------------------------------------------------

export async function fetchMappings(
  token: string,
  params?: {
    sourceId?: string;
    mappingType?: OPCUAMappingType;
    isEnabled?: boolean;
    offset?: number;
    limit?: number;
  },
): Promise<OPCUAMappingListResponse> {
  const query = new URLSearchParams();
  if (params?.sourceId != null) query.set('sourceId', params.sourceId);
  if (params?.mappingType != null) query.set('mappingType', params.mappingType);
  if (params?.isEnabled != null) query.set('isEnabled', String(params.isEnabled));
  if (params?.offset != null) query.set('offset', String(params.offset));
  if (params?.limit != null) query.set('limit', String(params.limit));
  const qs = query.toString();

  const res = await tenantApiFetch(`/opcua/mappings${qs ? `?${qs}` : ''}`, {}, token);
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to list OPC UA mappings'));
  return res.json() as Promise<OPCUAMappingListResponse>;
}

export async function createMapping(
  token: string,
  data: OPCUAMappingCreateInput,
): Promise<OPCUAMappingResponse> {
  const res = await tenantApiFetch(
    '/opcua/mappings',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to create OPC UA mapping'));
  return res.json() as Promise<OPCUAMappingResponse>;
}

export async function fetchMapping(
  token: string,
  mappingId: string,
): Promise<OPCUAMappingResponse> {
  const res = await tenantApiFetch(
    `/opcua/mappings/${encodeURIComponent(mappingId)}`,
    {},
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to fetch OPC UA mapping'));
  return res.json() as Promise<OPCUAMappingResponse>;
}

export async function updateMapping(
  token: string,
  mappingId: string,
  data: OPCUAMappingUpdateInput,
): Promise<OPCUAMappingResponse> {
  const res = await tenantApiFetch(
    `/opcua/mappings/${encodeURIComponent(mappingId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to update OPC UA mapping'));
  return res.json() as Promise<OPCUAMappingResponse>;
}

export async function deleteMapping(
  token: string,
  mappingId: string,
): Promise<void> {
  const res = await tenantApiFetch(
    `/opcua/mappings/${encodeURIComponent(mappingId)}`,
    { method: 'DELETE' },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok) throw new Error(await getApiErrorMessage(res, 'Failed to delete OPC UA mapping'));
}

export async function validateMapping(
  token: string,
  mappingId: string,
): Promise<MappingValidationResult> {
  const res = await tenantApiFetch(
    `/opcua/mappings/${encodeURIComponent(mappingId)}/validate`,
    { method: 'POST' },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to validate OPC UA mapping'));
  return res.json() as Promise<MappingValidationResult>;
}

export async function dryRunMapping(
  token: string,
  mappingId: string,
  revisionJson?: Record<string, unknown>,
): Promise<MappingDryRunResult> {
  const body = revisionJson != null ? JSON.stringify({ revisionJson }) : undefined;
  const headers: Record<string, string> = {};
  if (body != null) headers['Content-Type'] = 'application/json';

  const res = await tenantApiFetch(
    `/opcua/mappings/${encodeURIComponent(mappingId)}/dry-run`,
    {
      method: 'POST',
      ...(body != null ? { headers, body } : {}),
    },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to dry-run OPC UA mapping'));
  return res.json() as Promise<MappingDryRunResult>;
}

// ---------------------------------------------------------------------------
// Dataspace API functions
// ---------------------------------------------------------------------------

export async function publishToDataspace(
  token: string,
  data: DataspacePublishInput,
): Promise<DataspacePublicationJobResponse> {
  const res = await tenantApiFetch(
    '/opcua/dataspace/publish',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to publish to dataspace'));
  return res.json() as Promise<DataspacePublicationJobResponse>;
}

export async function fetchPublicationJobs(
  token: string,
  params?: { dppId?: string; offset?: number; limit?: number },
): Promise<DataspacePublicationJobListResponse> {
  const query = new URLSearchParams();
  if (params?.dppId != null) query.set('dppId', params.dppId);
  if (params?.offset != null) query.set('offset', String(params.offset));
  if (params?.limit != null) query.set('limit', String(params.limit));
  const qs = query.toString();

  const res = await tenantApiFetch(`/opcua/dataspace/jobs${qs ? `?${qs}` : ''}`, {}, token);
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to list dataspace publication jobs'));
  return res.json() as Promise<DataspacePublicationJobListResponse>;
}

export async function fetchPublicationJob(
  token: string,
  jobId: string,
): Promise<DataspacePublicationJobResponse> {
  const res = await tenantApiFetch(
    `/opcua/dataspace/jobs/${encodeURIComponent(jobId)}`,
    {},
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to fetch dataspace publication job'));
  return res.json() as Promise<DataspacePublicationJobResponse>;
}

export async function retryPublicationJob(
  token: string,
  jobId: string,
): Promise<DataspacePublicationJobResponse> {
  const res = await tenantApiFetch(
    `/opcua/dataspace/jobs/${encodeURIComponent(jobId)}/retry`,
    { method: 'POST' },
    token,
  );
  checkFeatureEnabled(res);
  if (!res.ok)
    throw new Error(await getApiErrorMessage(res, 'Failed to retry dataspace publication job'));
  return res.json() as Promise<DataspacePublicationJobResponse>;
}
