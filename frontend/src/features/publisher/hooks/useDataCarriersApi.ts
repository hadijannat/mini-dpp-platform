import { useCallback } from 'react';
import type {
  DataCarrierCreateRequest,
  DataCarrierDeprecateRequest,
  DataCarrierListResponse,
  DataCarrierPreSalePackResponse,
  DataCarrierQAResponse,
  DataCarrierQualityCheckCreateRequest,
  DataCarrierQualityCheckResponse,
  DataCarrierRegistryExportResponse,
  DataCarrierRenderRequest,
  DataCarrierReissueRequest,
  DataCarrierResponse,
  DataCarrierUpdateRequest,
  DataCarrierValidationRequest,
  DataCarrierValidationResponse,
  DataCarrierWithdrawRequest,
} from '@/api/types';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';

type RegistryExportFormat = 'json' | 'csv';

type CarrierListFilters = {
  dppId?: string;
  status?: 'active' | 'deprecated' | 'withdrawn';
  identityLevel?: 'model' | 'batch' | 'item';
  identifierScheme?: 'gs1_gtin' | 'iec61406' | 'direct_url';
};

async function parseJsonOrThrow<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, fallback));
  }
  return (await response.json()) as T;
}

function buildListQuery(filters: CarrierListFilters): string {
  const params = new URLSearchParams();
  if (filters.dppId) params.set('dpp_id', filters.dppId);
  if (filters.status) params.set('status', filters.status);
  if (filters.identityLevel) params.set('identity_level', filters.identityLevel);
  if (filters.identifierScheme) params.set('identifier_scheme', filters.identifierScheme);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export function useDataCarriersApi(token?: string) {
  const listCarriers = useCallback(
    async (filters: CarrierListFilters = {}): Promise<DataCarrierListResponse> => {
      const response = await tenantApiFetch(
        `/data-carriers${buildListQuery(filters)}`,
        {},
        token
      );
      return parseJsonOrThrow<DataCarrierListResponse>(response, 'Failed to load data carriers');
    },
    [token]
  );

  const createCarrier = useCallback(
    async (payload: DataCarrierCreateRequest): Promise<DataCarrierResponse> => {
      const response = await tenantApiFetch(
        '/data-carriers',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        token
      );
      return parseJsonOrThrow<DataCarrierResponse>(response, 'Failed to create data carrier');
    },
    [token]
  );

  const getCarrier = useCallback(
    async (carrierId: string): Promise<DataCarrierResponse> => {
      const response = await tenantApiFetch(`/data-carriers/${carrierId}`, {}, token);
      return parseJsonOrThrow<DataCarrierResponse>(response, 'Failed to load data carrier');
    },
    [token]
  );

  const updateCarrier = useCallback(
    async (
      carrierId: string,
      payload: DataCarrierUpdateRequest
    ): Promise<DataCarrierResponse> => {
      const response = await tenantApiFetch(
        `/data-carriers/${carrierId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        token
      );
      return parseJsonOrThrow<DataCarrierResponse>(response, 'Failed to update data carrier');
    },
    [token]
  );

  const renderCarrier = useCallback(
    async (carrierId: string, payload: DataCarrierRenderRequest): Promise<Blob> => {
      const response = await tenantApiFetch(
        `/data-carriers/${carrierId}/render`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        token
      );
      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, 'Failed to render data carrier'));
      }
      return response.blob();
    },
    [token]
  );

  const validateCarrierPayload = useCallback(
    async (
      payload: DataCarrierValidationRequest
    ): Promise<DataCarrierValidationResponse> => {
      const response = await tenantApiFetch(
        '/data-carriers/validate',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        token
      );
      return parseJsonOrThrow<DataCarrierValidationResponse>(
        response,
        'Failed to validate carrier payload'
      );
    },
    [token]
  );

  const getCarrierQa = useCallback(
    async (carrierId: string): Promise<DataCarrierQAResponse> => {
      const response = await tenantApiFetch(`/data-carriers/${carrierId}/qa`, {}, token);
      return parseJsonOrThrow<DataCarrierQAResponse>(response, 'Failed to load carrier QA');
    },
    [token]
  );

  const createQualityCheck = useCallback(
    async (
      carrierId: string,
      payload: DataCarrierQualityCheckCreateRequest
    ): Promise<DataCarrierQualityCheckResponse> => {
      const response = await tenantApiFetch(
        `/data-carriers/${carrierId}/quality-checks`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        token
      );
      return parseJsonOrThrow<DataCarrierQualityCheckResponse>(
        response,
        'Failed to create quality check'
      );
    },
    [token]
  );

  const deprecateCarrier = useCallback(
    async (
      carrierId: string,
      payload: DataCarrierDeprecateRequest = {}
    ): Promise<DataCarrierResponse> => {
      const response = await tenantApiFetch(
        `/data-carriers/${carrierId}/lifecycle/deprecate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        token
      );
      return parseJsonOrThrow<DataCarrierResponse>(response, 'Failed to deprecate data carrier');
    },
    [token]
  );

  const withdrawCarrier = useCallback(
    async (carrierId: string, payload: DataCarrierWithdrawRequest): Promise<DataCarrierResponse> => {
      const response = await tenantApiFetch(
        `/data-carriers/${carrierId}/lifecycle/withdraw`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        token
      );
      return parseJsonOrThrow<DataCarrierResponse>(response, 'Failed to withdraw data carrier');
    },
    [token]
  );

  const reissueCarrier = useCallback(
    async (
      carrierId: string,
      payload: DataCarrierReissueRequest = {}
    ): Promise<DataCarrierResponse> => {
      const response = await tenantApiFetch(
        `/data-carriers/${carrierId}/lifecycle/reissue`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        token
      );
      return parseJsonOrThrow<DataCarrierResponse>(response, 'Failed to reissue data carrier');
    },
    [token]
  );

  const getPreSalePack = useCallback(
    async (carrierId: string): Promise<DataCarrierPreSalePackResponse> => {
      const response = await tenantApiFetch(`/data-carriers/${carrierId}/pre-sale-pack`, {}, token);
      return parseJsonOrThrow<DataCarrierPreSalePackResponse>(
        response,
        'Failed to load pre-sale pack'
      );
    },
    [token]
  );

  const exportRegistry = useCallback(
    async (
      format: RegistryExportFormat
    ): Promise<DataCarrierRegistryExportResponse | Blob> => {
      const response = await tenantApiFetch(
        `/data-carriers/registry-export?format=${format}`,
        {},
        token
      );
      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, 'Failed to export data carrier registry'));
      }
      if (format === 'csv') {
        return response.blob();
      }
      return (await response.json()) as DataCarrierRegistryExportResponse;
    },
    [token]
  );

  return {
    listCarriers,
    createCarrier,
    getCarrier,
    updateCarrier,
    renderCarrier,
    validateCarrierPayload,
    getCarrierQa,
    createQualityCheck,
    deprecateCarrier,
    withdrawCarrier,
    reissueCarrier,
    getPreSalePack,
    exportRegistry,
  };
}
