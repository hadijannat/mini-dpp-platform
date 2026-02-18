// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

const authState = {
  user: { access_token: 'token-123', profile: {} },
  isAuthenticated: true,
  isLoading: false,
};

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

const tenantApiFetchMock = vi.fn();

vi.mock('@/lib/api', () => ({
  tenantApiFetch: (...args: unknown[]) => tenantApiFetchMock(...args),
  getApiErrorMessage: vi.fn().mockResolvedValue('API error'),
}));

import RoleRequestsPage from './RoleRequestsPage';

describe('RoleRequestsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders requester identity fields and pending review actions', async () => {
    tenantApiFetchMock.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: 'req-1',
            user_subject: 'subject-123',
            requester_email: 'requester@example.com',
            requester_display_name: 'Requester User',
            requested_role: 'publisher',
            status: 'pending',
            reason: 'Need publishing rights',
            reviewed_by: null,
            review_note: null,
            reviewed_at: null,
            created_at: '2026-02-18T10:00:00Z',
          },
        ]),
    });

    render(<RoleRequestsPage />);

    await waitFor(() => {
      expect(screen.getByText('Requester User')).toBeTruthy();
    });

    expect(screen.getByText('requester@example.com')).toBeTruthy();
    expect(screen.getByText('subject-123')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Approve' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Deny' })).toBeTruthy();
  });
});
