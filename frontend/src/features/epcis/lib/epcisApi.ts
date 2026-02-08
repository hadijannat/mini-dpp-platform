import { apiFetch, tenantApiFetch, getApiErrorMessage } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types — mirrors backend EPCISEventResponse
// ---------------------------------------------------------------------------

export type EPCISEventType =
  | 'ObjectEvent'
  | 'AggregationEvent'
  | 'TransactionEvent'
  | 'TransformationEvent'
  | 'AssociationEvent';

export interface EPCISEvent {
  id: string;
  dpp_id: string;
  event_id: string;
  event_type: EPCISEventType;
  event_time: string;
  event_time_zone_offset: string;
  action: string | null;
  biz_step: string | null;
  disposition: string | null;
  read_point: string | null;
  biz_location: string | null;
  payload: Record<string, unknown>;
  error_declaration: Record<string, unknown> | null;
  created_by_subject: string;
  created_at: string;
}

export interface EPCISQueryResponse {
  '@context': string[];
  type: string;
  eventList: EPCISEvent[];
}

export interface CaptureResponse {
  captureId: string;
  eventCount: number;
}

export interface EPCISQueryFilters {
  event_type?: EPCISEventType;
  GE_eventTime?: string;
  LT_eventTime?: string;
  EQ_bizStep?: string;
  EQ_disposition?: string;
  MATCH_epc?: string;
  dpp_id?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// CBV 2.0 vocabularies (static — GS1 standard values)
// ---------------------------------------------------------------------------

export const EVENT_TYPES: EPCISEventType[] = [
  'ObjectEvent',
  'AggregationEvent',
  'TransactionEvent',
  'TransformationEvent',
  'AssociationEvent',
];

export const BIZ_STEPS = [
  'accepting', 'arriving', 'assembling', 'collecting', 'commissioning',
  'decommissioning', 'departing', 'destroying', 'disassembling', 'encoding',
  'holding', 'inspecting', 'installing', 'loading', 'packing', 'picking',
  'receiving', 'repairing', 'replacing', 'shipping', 'storing', 'transforming',
  'uninstalling', 'unloading', 'unpacking', 'void',
] as const;

export const DISPOSITIONS = [
  'active', 'conformant', 'container_closed', 'container_open', 'damaged',
  'destroyed', 'disposed', 'encoded', 'in_progress', 'in_transit', 'inactive',
  'no_pedigree_match', 'non_conformant', 'recalled', 'reserved', 'returned',
  'sold', 'unknown',
] as const;

export const ACTIONS = ['ADD', 'OBSERVE', 'DELETE'] as const;

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchPublicEPCISEvents(
  tenantSlug: string,
  dppId: string,
): Promise<EPCISQueryResponse> {
  const response = await apiFetch(
    `/api/v1/public/${encodeURIComponent(tenantSlug)}/epcis/events/${encodeURIComponent(dppId)}`,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch EPCIS events'));
  }
  return response.json() as Promise<EPCISQueryResponse>;
}

export async function fetchEPCISEvents(
  filters: EPCISQueryFilters,
  token?: string,
): Promise<EPCISQueryResponse> {
  const params = new URLSearchParams();
  if (filters.event_type) params.set('event_type', filters.event_type);
  if (filters.GE_eventTime) params.set('GE_eventTime', filters.GE_eventTime);
  if (filters.LT_eventTime) params.set('LT_eventTime', filters.LT_eventTime);
  if (filters.EQ_bizStep) params.set('EQ_bizStep', filters.EQ_bizStep);
  if (filters.EQ_disposition) params.set('EQ_disposition', filters.EQ_disposition);
  if (filters.MATCH_epc) params.set('MATCH_epc', filters.MATCH_epc);
  if (filters.dpp_id) params.set('dpp_id', filters.dpp_id);
  if (filters.limit != null) params.set('limit', String(filters.limit));
  if (filters.offset != null) params.set('offset', String(filters.offset));

  const qs = params.toString();
  const response = await tenantApiFetch(`/epcis/events${qs ? `?${qs}` : ''}`, {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch EPCIS events'));
  }
  return response.json() as Promise<EPCISQueryResponse>;
}

export async function fetchEPCISEvent(
  eventId: string,
  token?: string,
): Promise<EPCISEvent> {
  const response = await tenantApiFetch(
    `/epcis/events/${encodeURIComponent(eventId)}`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch EPCIS event'));
  }
  return response.json() as Promise<EPCISEvent>;
}

export async function captureEPCISEvents(
  dppId: string,
  document: Record<string, unknown>,
  token?: string,
): Promise<CaptureResponse> {
  const response = await tenantApiFetch(
    `/epcis/capture?dpp_id=${encodeURIComponent(dppId)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(document),
    },
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to capture EPCIS events'));
  }
  return response.json() as Promise<CaptureResponse>;
}
