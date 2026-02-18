// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const authState = {
  user: { profile: { roles: ['viewer'] } },
  signoutRedirect: vi.fn(),
};

vi.mock('react-oidc-context', () => ({
  useAuth: () => authState,
}));

vi.mock('@/lib/breadcrumbs', () => ({
  useBreadcrumbs: () => [],
}));

vi.mock('../components/SidebarNav', () => ({
  default: ({ navigation }: { navigation: Array<{ name: string }> }) => (
    <nav>
      {navigation.map((item) => (
        <span key={item.name}>{item.name}</span>
      ))}
    </nav>
  ),
}));

vi.mock('../components/SidebarUserFooter', () => ({
  default: () => <div>Sidebar footer</div>,
}));

import PublisherLayout from './PublisherLayout';

describe('PublisherLayout role request navigation', () => {
  beforeEach(() => {
    authState.user = { profile: { roles: ['viewer'] } };
  });

  it('shows Role Requests for tenant_admin users', () => {
    authState.user = { profile: { roles: ['tenant_admin'] } };

    render(
      <MemoryRouter>
        <PublisherLayout />
      </MemoryRouter>,
    );

    expect(screen.queryAllByText('Role Requests').length).toBeGreaterThan(0);
    expect(screen.queryAllByText('Admin').length).toBe(0);
  });

  it('shows Role Requests and Admin navigation for platform admin users', () => {
    authState.user = { profile: { roles: ['admin'] } };

    render(
      <MemoryRouter>
        <PublisherLayout />
      </MemoryRouter>,
    );

    expect(screen.queryAllByText('Role Requests').length).toBeGreaterThan(0);
    expect(screen.queryAllByText('Admin').length).toBeGreaterThan(0);
  });
});
