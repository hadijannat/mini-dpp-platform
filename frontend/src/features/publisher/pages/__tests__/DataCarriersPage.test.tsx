// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mockTenantApiFetch = vi.fn();

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: { access_token: 'fake-token' },
    isAuthenticated: true,
    signinRedirect: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  tenantApiFetch: (...args: unknown[]) => mockTenantApiFetch(...args),
  getApiErrorMessage: vi.fn(() => Promise.resolve('Request failed')),
}));

function jsonResponse(data: unknown) {
  return {
    ok: true,
    json: () => Promise.resolve(data),
    blob: () => Promise.resolve(new Blob(['img'])),
  };
}

describe('DataCarriersPage', () => {
  beforeEach(() => {
    mockTenantApiFetch.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/dpps') {
        return Promise.resolve(
          jsonResponse([
            {
              id: 'dpp-1',
              status: 'published',
              asset_ids: {
                manufacturerPartId: 'PART-1',
                serialNumber: 'SER-1',
                gtin: '10614141000415',
              },
              created_at: '2026-01-01T00:00:00Z',
            },
          ]),
        );
      }
      if (path.startsWith('/data-carriers?')) {
        return Promise.resolve(jsonResponse({ items: [], count: 0 }));
      }
      if (path === '/data-carriers' && options?.method === 'POST') {
        return Promise.resolve(
          jsonResponse({
            id: 'carrier-1',
            dpp_id: 'dpp-1',
            identity_level: 'item',
            identifier_scheme: 'direct_url',
            carrier_type: 'qr',
            resolver_strategy: 'direct_public_dpp',
            status: 'active',
            identifier_key: 'direct_url:abc',
            identifier_data: { direct_url: 'https://example.com/passport' },
            encoded_uri: 'https://example.com/passport',
            pre_sale_enabled: true,
            is_gtin_verified: false,
          }),
        );
      }
      if (path === '/data-carriers/carrier-1/render') {
        return Promise.resolve({
          ok: true,
          blob: () => Promise.resolve(new Blob(['rendered'])),
        });
      }
      return Promise.resolve(jsonResponse({}));
    });
  });

  afterEach(() => {
    cleanup();
    mockTenantApiFetch.mockReset();
  });

  it('renders wizard and legacy compatibility section', async () => {
    const { default: DataCarriersPage } = await import('../DataCarriersPage');

    render(
      <MemoryRouter>
        <DataCarriersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Managed Carrier Wizard')).toBeTruthy();
    expect(screen.getByText('Legacy Quick QR (Compatibility)')).toBeTruthy();
  });

  it('creates a direct-url managed carrier via wizard flow', async () => {
    const { default: DataCarriersPage } = await import('../DataCarriersPage');

    render(
      <MemoryRouter>
        <DataCarriersPage />
      </MemoryRouter>,
    );

    await screen.findByRole('option', { name: /PART-1 - SER-1/i });
    const select = await screen.findByLabelText('Select Published DPP');
    fireEvent.change(select, { target: { value: 'dpp-1' } });

    fireEvent.click(screen.getByText('Next')); // Carrier Type

    const schemeSelect = screen.getByLabelText('Identifier scheme');
    fireEvent.change(schemeSelect, { target: { value: 'direct_url' } });

    fireEvent.click(screen.getByText('Next')); // Identifier Build

    fireEvent.change(screen.getByPlaceholderText('https://example.com/path'), {
      target: { value: 'https://example.com/passport' },
    });

    fireEvent.click(screen.getByText('Next')); // Resolver

    await waitFor(() => {
      expect((screen.getByText('Create Managed Carrier') as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(screen.getByText('Create Managed Carrier'));

    await waitFor(() => {
      expect(
        mockTenantApiFetch.mock.calls.some(
          ([path, options, token]) =>
            path === '/data-carriers' &&
            (options as RequestInit | undefined)?.method === 'POST' &&
            token === 'fake-token',
        ),
      ).toBe(true);
    });

    expect(await screen.findByText('Active carrier')).toBeTruthy();
  });
});
