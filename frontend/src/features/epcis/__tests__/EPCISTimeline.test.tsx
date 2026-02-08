// @vitest-environment jsdom
import { describe, expect, it, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { EPCISTimeline } from '../components/EPCISTimeline';
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
    payload: {},
    error_declaration: null,
    created_by_subject: 'test-user',
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe('EPCISTimeline', () => {
  afterEach(() => cleanup());
  it('renders empty state when no events', () => {
    render(<EPCISTimeline events={[]} />);
    expect(screen.getByText('No supply chain events')).toBeTruthy();
  });

  it('renders timeline with events', () => {
    const events = [
      mockEvent({ id: 'e1', event_type: 'ObjectEvent', biz_step: 'shipping' }),
      mockEvent({ id: 'e2', event_type: 'AggregationEvent', biz_step: 'packing' }),
    ];

    render(<EPCISTimeline events={events} />);

    expect(screen.getByText('Object')).toBeTruthy();
    expect(screen.getByText('Aggregation')).toBeTruthy();
    expect(screen.getByText('shipping')).toBeTruthy();
    expect(screen.getByText('packing')).toBeTruthy();
  });

  it('renders correct number of EventCards', () => {
    const events = [
      mockEvent({ id: 'e1' }),
      mockEvent({ id: 'e2' }),
      mockEvent({ id: 'e3' }),
    ];

    render(<EPCISTimeline events={events} />);

    // Each EventCard renders as a clickable element with role="button"
    const cards = screen.getAllByRole('button');
    expect(cards).toHaveLength(3);
  });
});
