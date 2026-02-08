// @vitest-environment jsdom
import { describe, expect, it, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { EventDetailDialog } from '../components/EventDetailDialog';
import type { EPCISEvent } from '../lib/epcisApi';

function mockEvent(overrides: Partial<EPCISEvent> = {}): EPCISEvent {
  return {
    id: 'evt-1',
    dpp_id: 'dpp-abc',
    event_id: 'urn:uuid:test-event-1',
    event_type: 'ObjectEvent',
    event_time: new Date().toISOString(),
    event_time_zone_offset: '+00:00',
    action: 'OBSERVE',
    biz_step: 'shipping',
    disposition: 'in_transit',
    read_point: null,
    biz_location: null,
    payload: { epcList: ['urn:epc:id:sgtin:0614141.107346.2017'] },
    error_declaration: null,
    created_by_subject: 'test-user',
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe('EventDetailDialog', () => {
  afterEach(() => cleanup());

  it('returns null when event is null', () => {
    const { container } = render(
      <EventDetailDialog event={null} open={true} onOpenChange={() => {}} />,
    );
    // When event is null, the component returns null — nothing rendered
    expect(container.innerHTML).toBe('');
  });

  it('shows event fields when event is provided', () => {
    const event = mockEvent({ event_id: 'urn:uuid:abc-123' });
    render(<EventDetailDialog event={event} open={true} onOpenChange={() => {}} />);
    expect(screen.getByText('Event ID')).toBeTruthy();
    expect(screen.getByText('Event Time')).toBeTruthy();
    expect(screen.getByText('Timezone')).toBeTruthy();
    expect(screen.getByText('+00:00')).toBeTruthy();
    expect(screen.getByText('DPP ID')).toBeTruthy();
    expect(screen.getByText('dpp-abc')).toBeTruthy();
  });

  it('shows payload JSON', () => {
    const event = mockEvent({ payload: { key: 'value' } });
    render(<EventDetailDialog event={event} open={true} onOpenChange={() => {}} />);
    expect(screen.getByText('Event Payload')).toBeTruthy();
    // The payload is rendered as formatted JSON
    expect(screen.getByText(/"key": "value"/)).toBeTruthy();
  });

  it('shows error declaration when present', () => {
    const event = mockEvent({
      error_declaration: { declarationTime: '2026-01-01T00:00:00Z', reason: 'incorrect_data' },
    });
    render(<EventDetailDialog event={event} open={true} onOpenChange={() => {}} />);
    expect(screen.getByText('Error Declaration')).toBeTruthy();
    expect(screen.getByText(/"reason": "incorrect_data"/)).toBeTruthy();
  });

  it('does not show error declaration section when not present', () => {
    const event = mockEvent({ error_declaration: null });
    render(<EventDetailDialog event={event} open={true} onOpenChange={() => {}} />);
    expect(screen.queryByText('Error Declaration')).toBeNull();
  });
});
