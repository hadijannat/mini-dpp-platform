// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PublicIdtaSubmodelEditorPage from '../pages/PublicIdtaSubmodelEditorPage';

const listPublicTemplatesMock = vi.fn();
const getPublicTemplateMock = vi.fn();
const listPublicTemplateVersionsMock = vi.fn();
const getPublicTemplateContractMock = vi.fn();
const previewPublicTemplateMock = vi.fn();
const exportPublicTemplateMock = vi.fn();

vi.mock('../lib/publicSmtApi', () => ({
  listPublicTemplates: (...args: unknown[]) => listPublicTemplatesMock(...args),
  getPublicTemplate: (...args: unknown[]) => getPublicTemplateMock(...args),
  listPublicTemplateVersions: (...args: unknown[]) => listPublicTemplateVersionsMock(...args),
  getPublicTemplateContract: (...args: unknown[]) => getPublicTemplateContractMock(...args),
  previewPublicTemplate: (...args: unknown[]) => previewPublicTemplateMock(...args),
  exportPublicTemplate: (...args: unknown[]) => exportPublicTemplateMock(...args),
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
    vi.clearAllMocks();

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

    previewPublicTemplateMock.mockResolvedValue({
      template_key: 'digital-nameplate',
      version: '3.0.1',
      warnings: [],
      aas_environment: { submodels: [] },
    });

    exportPublicTemplateMock.mockResolvedValue({
      blob: new Blob(['{}'], { type: 'application/json' }),
      filename: 'digital-nameplate-3.0.1.json',
      contentType: 'application/json',
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

  it('exports JSON via public API', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Export JSON/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: /Export JSON/i }));

    await waitFor(() => {
      expect(exportPublicTemplateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          template_key: 'digital-nameplate',
          format: 'json',
        }),
      );
    });
  });
});
