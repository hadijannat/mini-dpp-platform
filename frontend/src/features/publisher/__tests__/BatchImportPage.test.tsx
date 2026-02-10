// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'fake-token' },
    isAuthenticated: true,
    signinRedirect: vi.fn(),
  }),
}));

vi.mock('@/lib/tenant', () => ({
  getTenantSlug: () => 'default',
  useTenantSlug: () => ['default', vi.fn()],
}));

let mockApiResponse: { ok: boolean; json: () => Promise<unknown> } = {
  ok: true,
  json: () =>
    Promise.resolve({
      total: 2,
      succeeded: 2,
      failed: 0,
      results: [
        { index: 0, dpp_id: 'aaa-bbb-ccc', status: 'ok', error: null },
        { index: 1, dpp_id: 'ddd-eee-fff', status: 'ok', error: null },
      ],
    }),
};

vi.mock('@/lib/api', () => ({
  tenantApiFetch: vi.fn(() => Promise.resolve(mockApiResponse)),
  getApiErrorMessage: vi.fn(() => Promise.resolve('Import failed')),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { default: BatchImportPage } = await import('../pages/BatchImportPage');

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BatchImportPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('BatchImportPage', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    mockApiResponse = {
      ok: true,
      json: () =>
        Promise.resolve({
          total: 2,
          succeeded: 2,
          failed: 0,
          results: [
            { index: 0, dpp_id: 'aaa-bbb-ccc', status: 'ok', error: null },
            { index: 1, dpp_id: 'ddd-eee-fff', status: 'ok', error: null },
          ],
        }),
    };
  });

  it('renders page header and upload area', async () => {
    await renderPage();
    expect(screen.getByText('Batch Import')).toBeTruthy();
    expect(screen.getByText('Upload JSON')).toBeTruthy();
    expect(screen.getByText('Import DPPs')).toBeTruthy();
  });

  it('disables import button when textarea is empty', async () => {
    await renderPage();
    const button = screen.getByText('Import DPPs');
    expect(button.closest('button')?.disabled).toBe(true);
  });

  it('enables import button when JSON is entered', async () => {
    await renderPage();
    const textarea = screen.getByPlaceholderText(/manufacturerPartId/);
    fireEvent.change(textarea, {
      target: { value: '[{"asset_ids": {"manufacturerPartId": "P-1"}}]' },
    });
    const button = screen.getByText('Import DPPs');
    expect(button.closest('button')?.disabled).toBe(false);
  });

  it('shows results table after successful import', async () => {
    await renderPage();
    const textarea = screen.getByPlaceholderText(/manufacturerPartId/);
    fireEvent.change(textarea, {
      target: { value: '[{"asset_ids": {"manufacturerPartId": "P-1"}}]' },
    });
    fireEvent.click(screen.getByText('Import DPPs'));

    await waitFor(() => {
      expect(screen.getByText('Import Results')).toBeTruthy();
    });
    expect(screen.getByText('2 succeeded')).toBeTruthy();
  });

  it('shows error when JSON is invalid', async () => {
    await renderPage();
    const textarea = screen.getByPlaceholderText(/manufacturerPartId/);
    fireEvent.change(textarea, { target: { value: '{not valid json' } });
    fireEvent.click(screen.getByText('Import DPPs'));

    await waitFor(() => {
      // JSON.parse throws SyntaxError — should be shown
      expect(screen.getByRole('alert')).toBeTruthy();
    });
  });

  it('shows error when JSON is not an array', async () => {
    await renderPage();
    const textarea = screen.getByPlaceholderText(/manufacturerPartId/);
    fireEvent.change(textarea, { target: { value: '{"name": "not-array"}' } });
    fireEvent.click(screen.getByText('Import DPPs'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
  });
});
