// @vitest-environment jsdom
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CaptureDialog } from '../components/CaptureDialog';

vi.mock('react-oidc-context', () => ({
  useAuth: () => ({ user: { access_token: 'test-token' } }),
}));

function renderDialog(open = true) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CaptureDialog open={open} onOpenChange={() => {}} dppId="dpp-123" />
    </QueryClientProvider>,
  );
}

describe('CaptureDialog', () => {
  afterEach(() => cleanup());

  it('renders dialog title when open', () => {
    renderDialog(true);
    expect(screen.getByText('Capture EPCIS Event')).toBeTruthy();
  });

  it('renders event type select with default ObjectEvent', () => {
    renderDialog(true);
    // Radix Select renders options only when opened. The trigger shows the
    // currently selected value. Default is ObjectEvent -> "Object Event".
    expect(screen.getByText('Object Event')).toBeTruthy();
    // The Label for the select is present
    expect(screen.getByText('Event Type')).toBeTruthy();
  });

  it('shows action select for ObjectEvent (default)', () => {
    renderDialog(true);
    // The default event type is ObjectEvent which needs an Action select.
    // The label "Action" should be present.
    expect(screen.getByText('Action')).toBeTruthy();
  });

  it('shows EPC list input for ObjectEvent (default)', () => {
    renderDialog(true);
    // ObjectEvent shows "EPCs (comma-separated)" label
    expect(screen.getByText('EPCs (comma-separated)')).toBeTruthy();
  });

  it('renders Capture Event and Cancel buttons', () => {
    renderDialog(true);
    expect(screen.getByText('Capture Event')).toBeTruthy();
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('renders common fields (Business Step, Disposition, Read Point, Business Location)', () => {
    renderDialog(true);
    expect(screen.getByText('Business Step')).toBeTruthy();
    expect(screen.getByText('Disposition')).toBeTruthy();
    expect(screen.getByText('Read Point')).toBeTruthy();
    expect(screen.getByText('Business Location')).toBeTruthy();
  });
});
