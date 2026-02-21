// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PublicIdtaSubmodelEditorPage from '../pages/PublicIdtaSubmodelEditorPage';
import { SMT_DRAFT_STORAGE_KEY } from '../lib/smtDraftStorage';
import { PublicSmtApiError } from '../lib/publicSmtErrors';

const listPublicTemplatesMock = vi.fn();
const getPublicTemplateMock = vi.fn();
const listPublicTemplateVersionsMock = vi.fn();
const getPublicTemplateContractMock = vi.fn();
const previewPublicTemplateWithMetaMock = vi.fn();
const exportPublicTemplateWithMetaMock = vi.fn();

vi.mock('../lib/publicSmtApi', () => ({
  listPublicTemplates: (...args: unknown[]) => listPublicTemplatesMock(...args),
  getPublicTemplate: (...args: unknown[]) => getPublicTemplateMock(...args),
  listPublicTemplateVersions: (...args: unknown[]) => listPublicTemplateVersionsMock(...args),
  getPublicTemplateContract: (...args: unknown[]) => getPublicTemplateContractMock(...args),
  previewPublicTemplateWithMeta: (...args: unknown[]) => previewPublicTemplateWithMetaMock(...args),
  exportPublicTemplateWithMeta: (...args: unknown[]) => exportPublicTemplateWithMetaMock(...args),
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <PublicIdtaSubmodelEditorPage />
    </QueryClientProvider>,
  );
}

describe('PublicIdtaSubmodelEditorPage', () => {
  beforeEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.removeItem(SMT_DRAFT_STORAGE_KEY);
    window.localStorage.removeItem('publicSmt.autoPreview.enabled');
    window.localStorage.removeItem('publicSmt.autoPreview.background');

    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:test'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    });

    listPublicTemplatesMock.mockResolvedValue({
      templates: [
        {
          template_key: 'digital-nameplate',
          display_name: 'Digital Nameplate',
          catalog_status: 'published',
          semantic_id: 'https://admin-shell.io/zvei/nameplate/3/0/Nameplate',
          latest_version: '3.0.1',
          fetched_at: '2026-02-20T00:00:00Z',
          source_metadata: {
            resolved_version: '3.0.1',
            source_repo_ref: 'main',
            source_url: 'https://example.test',
          },
        },
      ],
      count: 1,
      status_filter: 'published',
    });

    getPublicTemplateMock.mockResolvedValue({
      template_key: 'digital-nameplate',
      display_name: 'Digital Nameplate',
      catalog_status: 'published',
      semantic_id: 'https://admin-shell.io/zvei/nameplate/3/0/Nameplate',
      latest_version: '3.0.1',
      fetched_at: '2026-02-20T00:00:00Z',
      source_metadata: {
        resolved_version: '3.0.1',
        source_repo_ref: 'main',
        source_file_sha: 'sha-123',
        source_url: 'https://example.test',
      },
      versions: [
        {
          version: '3.0.1',
          resolved_version: '3.0.1',
          status: 'published',
          is_default: true,
        },
      ],
    });

    listPublicTemplateVersionsMock.mockResolvedValue({
      template_key: 'digital-nameplate',
      count: 1,
      versions: [
        {
          version: '3.0.1',
          resolved_version: '3.0.1',
          status: 'published',
          is_default: true,
        },
      ],
    });

    getPublicTemplateContractMock.mockResolvedValue({
      template_key: 'digital-nameplate',
      idta_version: '3.0.1',
      semantic_id: 'https://admin-shell.io/zvei/nameplate/3/0/Nameplate',
      source_metadata: {
        resolved_version: '3.0.1',
        source_repo_ref: 'main',
        source_url: 'https://example.test',
      },
      definition: {
        submodel: {
          idShort: 'Nameplate',
          elements: [
            {
              modelType: 'Property',
              idShort: 'ManufacturerName',
              valueType: 'xs:string',
              smt: { cardinality: 'One' },
            },
          ],
        },
      },
      schema: {
        type: 'object',
        required: ['ManufacturerName'],
        properties: {
          ManufacturerName: { type: 'string' },
        },
      },
      dropin_resolution_report: [],
      unsupported_nodes: [],
      doc_hints: {},
    });

    previewPublicTemplateWithMetaMock.mockResolvedValue({
      data: {
        template_key: 'digital-nameplate',
        version: '3.0.1',
        warnings: [],
        aas_environment: { submodels: [] },
      },
      meta: {
        limit: 60,
        remaining: 59,
      },
    });

    exportPublicTemplateWithMetaMock.mockResolvedValue({
      result: {
        blob: new Blob(['{}'], { type: 'application/json' }),
        filename: 'digital-nameplate-3.0.1.json',
        contentType: 'application/json',
      },
      meta: {
        limit: 10,
        remaining: 9,
      },
    });
  });

  it('renders without auth and loads template contract', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/IDTA Submodel Template Editor/i)).toBeTruthy();
      expect(screen.getByText(/Sandbox Workspace/i)).toBeTruthy();
    });

    expect(screen.getByRole('button', { name: /Export JSON/i })).toBeTruthy();
  });

  it('does not trigger preview on initial load before user interaction', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Export JSON/i })).toBeTruthy();
    });

    expect(previewPublicTemplateWithMetaMock).not.toHaveBeenCalled();
  });

  it('does not auto-preview while editing form by default (preview-tab only)', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/ManufacturerName/i)).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText(/ManufacturerName/i), {
      target: { value: 'ACME Corp' },
    });

    await waitFor(() => {
      expect(previewPublicTemplateWithMetaMock).not.toHaveBeenCalled();
    });
  });

  it('runs background preview only after enabling the background toggle', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/ManufacturerName/i)).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText(/ManufacturerName/i), {
      target: { value: 'ACME Corp' },
    });

    await waitFor(() => {
      expect(previewPublicTemplateWithMetaMock).not.toHaveBeenCalled();
    });

    fireEvent.click(screen.getByLabelText(/Live preview in background/i));

    fireEvent.change(screen.getByLabelText(/ManufacturerName/i), {
      target: { value: 'ACME Corp Updated' },
    });

    await waitFor(() => {
      expect(previewPublicTemplateWithMetaMock).toHaveBeenCalledTimes(1);
    });
  });

  it('shows structured preview issues and jumps back to form from preview tab', async () => {
    previewPublicTemplateWithMetaMock.mockRejectedValue(
      new PublicSmtApiError('Template data failed validation', {
        status: 422,
        detail: {
          code: 'schema_validation_failed',
          message: 'Template data failed validation',
          errors: [{ path: 'ManufacturerName', message: 'Required', type: 'schema' }],
        },
      }),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/ManufacturerName/i)).toBeTruthy();
    });

    fireEvent.click(screen.getByLabelText(/Live preview in background/i));
    fireEvent.change(screen.getByLabelText(/ManufacturerName/i), {
      target: { value: 'ACME Corp Error' },
    });

    await waitFor(() => {
      expect(previewPublicTemplateWithMetaMock).toHaveBeenCalled();
      expect(screen.getByText(/ManufacturerName: Required/i)).toBeTruthy();
    });

    fireEvent.click(screen.getByText(/ManufacturerName: Required/i));

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Form/i }).getAttribute('data-state')).toBe('active');
    });
  });

  it('hides validation issues panel when there are no issues', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Export JSON/i })).toBeTruthy();
    });

    expect(screen.queryByLabelText(/Validation issues/i)).toBeNull();
  });

  it('disables auto preview and shows retry notice after 429', async () => {
    previewPublicTemplateWithMetaMock.mockRejectedValue(
      new PublicSmtApiError('Too many requests', {
        status: 429,
        rateLimit: {
          limit: 60,
          remaining: 0,
          retryAfterSeconds: 60,
        },
      }),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/ManufacturerName/i)).toBeTruthy();
    });

    fireEvent.click(screen.getByLabelText(/Live preview in background/i));
    fireEvent.change(screen.getByLabelText(/ManufacturerName/i), {
      target: { value: '429 Trigger' },
    });

    await waitFor(() => {
      expect(screen.getByText(/Retry after 60s/i)).toBeTruthy();
    });

    expect(screen.getByLabelText(/Auto preview \(Preview tab\)/i).getAttribute('data-state')).toBe('unchecked');

    fireEvent.change(screen.getByLabelText(/ManufacturerName/i), {
      target: { value: 'Another Value' },
    });

    await new Promise((resolve) => setTimeout(resolve, 500));
    expect(previewPublicTemplateWithMetaMock).toHaveBeenCalledTimes(1);
  });

  it('exports JSON via public API', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Export JSON/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: /Export JSON/i }));

    await waitFor(() => {
      expect(exportPublicTemplateWithMetaMock).toHaveBeenCalledWith(
        expect.objectContaining({
          template_key: 'digital-nameplate',
          format: 'json',
        }),
      );
    });
  });

  it('normalizes preview warnings so root placeholders are not rendered', async () => {
    previewPublicTemplateWithMetaMock.mockResolvedValue({
      data: {
        template_key: 'digital-nameplate',
        version: '3.0.1',
        warnings: ['root', 'root', "Submodel 'Nameplate' has no semanticId"],
        aas_environment: { submodels: [] },
      },
      meta: {
        limit: 60,
        remaining: 58,
      },
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /AAS JSON Preview/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByLabelText(/Live preview in background/i));
    fireEvent.change(screen.getByLabelText(/ManufacturerName/i), {
      target: { value: 'ACME Corp' },
    });

    await waitFor(() => {
      expect(previewPublicTemplateWithMetaMock).toHaveBeenCalled();
    });

    expect(screen.queryByText(/^root$/i)).toBeNull();
    expect(document.body.textContent).not.toContain('root | root');
  });

  it('shows contract diagnostics counts and entries', async () => {
    getPublicTemplateContractMock.mockResolvedValue({
      template_key: 'digital-nameplate',
      idta_version: '3.0.1',
      semantic_id: 'https://admin-shell.io/zvei/nameplate/3/0/Nameplate',
      source_metadata: {
        resolved_version: '3.0.1',
        source_repo_ref: 'main',
        source_url: 'https://example.test',
      },
      definition: {
        submodel: {
          idShort: 'Nameplate',
          elements: [
            {
              modelType: 'Property',
              idShort: 'ManufacturerName',
              valueType: 'xs:string',
              smt: { cardinality: 'One' },
            },
          ],
        },
      },
      schema: {
        type: 'object',
        required: ['ManufacturerName'],
        properties: {
          ManufacturerName: { type: 'string' },
        },
      },
      dropin_resolution_report: [
        { path: 'Nameplate.Address', status: 'unresolved', reason: 'source_not_found' },
        { path: 'Nameplate.ProductClass', status: 'resolved', reason: 'resolved' },
      ],
      unsupported_nodes: [
        {
          path: 'Nameplate.GenericItems',
          idShort: 'GenericItems',
          modelType: 'SubmodelElement',
          reasons: ['unsupported_model_type:SubmodelElement'],
        },
      ],
      doc_hints: {},
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Template diagnostics/i)).toBeTruthy();
      expect(screen.getByText(/Unsupported nodes: 1/i)).toBeTruthy();
      expect(screen.getByText(/Unresolved drop-ins: 1/i)).toBeTruthy();
    });

    expect(document.body.textContent).toContain('unsupported_model_type:SubmodelElement');
    expect(document.body.textContent).toContain('source_not_found');
  });

  it('seeds required list structure from schema so Carbon Footprint starts aligned', async () => {
    getPublicTemplateContractMock.mockResolvedValue({
      template_key: 'carbon-footprint',
      idta_version: '1.0.1',
      semantic_id: 'https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0',
      source_metadata: {
        resolved_version: '1.0.1',
        source_repo_ref: 'main',
        source_url: 'https://example.test',
      },
      definition: {
        submodel: {
          idShort: 'CarbonFootprint',
          elements: [
            {
              modelType: 'SubmodelElementList',
              idShort: 'ProductCarbonFootprints',
              displayName: { en: 'Product carbon footprint' },
              smt: { cardinality: 'One' },
              items: {
                modelType: 'SubmodelElementCollection',
                children: [
                  {
                    modelType: 'Property',
                    idShort: 'PcfCO2eq',
                    valueType: 'xs:decimal',
                    smt: { cardinality: 'One' },
                  },
                ],
              },
            },
          ],
        },
      },
      schema: {
        type: 'object',
        required: ['ProductCarbonFootprints'],
        properties: {
          ProductCarbonFootprints: {
            type: 'array',
            minItems: 1,
            items: {
              type: 'object',
              required: ['PcfCO2eq'],
              properties: {
                PcfCO2eq: { type: 'number' },
              },
            },
          },
        },
      },
      dropin_resolution_report: [],
      unsupported_nodes: [],
      doc_hints: {},
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/PcfCO2eq/i)).toBeTruthy();
    });

    expect(screen.queryByText(/No items yet/i)).toBeNull();
  });
});
