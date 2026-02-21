// @vitest-environment jsdom
import { expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import App from '@/App';

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    signinRedirect: vi.fn(),
  }),
}));

vi.mock('@/features/devtools/lib/publicSmtApi', () => ({
  listPublicTemplates: vi.fn().mockResolvedValue({
    templates: [],
    count: 0,
    status_filter: 'published',
  }),
  getPublicTemplate: vi.fn().mockResolvedValue(null),
  listPublicTemplateVersions: vi.fn().mockResolvedValue({ template_key: '', versions: [], count: 0 }),
  getPublicTemplateContract: vi.fn(),
  previewPublicTemplateWithMeta: vi.fn(),
  exportPublicTemplateWithMeta: vi.fn(),
}));

it('renders /tools/idta-submodel-editor without auth redirect', async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/tools/idta-submodel-editor']}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await waitFor(() => {
    expect(screen.getByText(/IDTA Submodel Template Editor/i)).toBeTruthy();
  });
});
