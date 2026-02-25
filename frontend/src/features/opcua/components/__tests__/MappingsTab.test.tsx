// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'fake-token', profile: { realm_access: { roles: ['publisher'] } } },
    isAuthenticated: true,
  }),
}));

vi.mock('@/lib/tenant', () => ({ getTenantSlug: () => 'default' }));

let mockApiResponse: unknown = { items: [], total: 0 };
let mockApiStatus = 200;

vi.mock('@/lib/api', () => ({
  tenantApiFetch: vi.fn(() =>
    Promise.resolve({
      ok: mockApiStatus >= 200 && mockApiStatus < 300,
      status: mockApiStatus,
      json: () => Promise.resolve(mockApiResponse),
    }),
  ),
  getApiErrorMessage: vi.fn(() => Promise.resolve('API Error')),
}));

async function renderTab() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { MappingsTab } = await import('../MappingsTab');
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <MappingsTab />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('MappingsTab', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockApiResponse = { items: [], total: 0 };
    mockApiStatus = 200;
  });

  it('renders empty state when no mappings exist', async () => {
    await renderTab();
    expect(await screen.findByText(/No mappings configured/)).toBeTruthy();
  });

  it('renders Add Mapping button', async () => {
    await renderTab();
    expect(await screen.findByText('Add Mapping')).toBeTruthy();
  });

  it('renders mappings table with type badges', async () => {
    mockApiResponse = {
      items: [
        {
          id: 'm1',
          tenant_id: 't1',
          source_id: 's1',
          nodeset_id: null,
          mapping_type: 'aas_patch',
          opcua_node_id: 'ns=2;s=Temperature',
          opcua_browse_path: null,
          opcua_datatype: 'Float',
          sampling_interval_ms: 1000,
          dpp_binding_mode: 'by_dpp_id',
          dpp_id: 'dpp-1',
          asset_id_query: null,
          target_template_key: 'nameplate',
          target_submodel_id: 'sm-1',
          target_aas_path: 'Nameplate.ManufacturerName',
          patch_op: 'replace',
          value_transform_expr: null,
          unit_hint: 'celsius',
          samm_aspect_urn: null,
          samm_property: null,
          samm_version: null,
          epcis_event_type: null,
          epcis_biz_step: null,
          epcis_disposition: null,
          epcis_action: null,
          epcis_read_point: null,
          epcis_biz_location: null,
          epcis_source_event_id_template: null,
          is_enabled: true,
          created_by: 'user',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
    };

    await renderTab();
    expect(await screen.findByText('ns=2;s=Temperature')).toBeTruthy();
    expect(screen.getByText('AAS Patch')).toBeTruthy();
    expect(screen.getByText('Nameplate.ManufacturerName')).toBeTruthy();
  });

  it('renders feature disabled banner on 410', async () => {
    mockApiStatus = 410;
    await renderTab();
    await waitFor(() => {
      expect(screen.getByText(/OPC UA integration is not enabled/)).toBeTruthy();
    });
  });
});
