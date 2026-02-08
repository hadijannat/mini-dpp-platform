// @vitest-environment jsdom
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { EventCard } from '../components/EventCard';
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

describe('EventCard', () => {
  afterEach(() => cleanup());

  it('renders event type badge and action badge', () => {
    render(<EventCard event={mockEvent()} />);
    expect(screen.getByText('Object')).toBeTruthy();
    expect(screen.getByText('OBSERVE')).toBeTruthy();
  });

  it('renders biz_step text', () => {
    render(<EventCard event={mockEvent({ biz_step: 'packing' })} />);
    expect(screen.getByText('packing')).toBeTruthy();
  });

  it('renders disposition text', () => {
    render(<EventCard event={mockEvent({ disposition: 'in_transit' })} />);
    expect(screen.getByText('in transit')).toBeTruthy();
  });

  it('fires onClick when clicked', () => {
    const onClick = vi.fn();
    render(<EventCard event={mockEvent()} onClick={onClick} />);
    const card = screen.getByRole('button');
    fireEvent.click(card);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('renders connector line when not last', () => {
    const { container } = render(<EventCard event={mockEvent()} isLast={false} />);
    // The connector line is a div with w-px class
    const line = container.querySelector('.w-px');
    expect(line).toBeTruthy();
  });

  it('does not render connector line when isLast', () => {
    const { container } = render(<EventCard event={mockEvent()} isLast={true} />);
    const line = container.querySelector('.w-px');
    expect(line).toBeNull();
  });
});
