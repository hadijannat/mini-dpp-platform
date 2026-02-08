// @vitest-environment jsdom
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { EventFilters } from '../components/EventFilters';
import type { EPCISQueryFilters } from '../lib/epcisApi';

const defaultFilters: EPCISQueryFilters = {};

describe('EventFilters', () => {
  afterEach(() => cleanup());

  it('renders event type, biz step, and disposition selects', () => {
    render(<EventFilters filters={defaultFilters} onChange={() => {}} />);
    // The default placeholder/value for all three selects
    expect(screen.getByText('All types')).toBeTruthy();
    expect(screen.getByText('All steps')).toBeTruthy();
    expect(screen.getByText('All dispositions')).toBeTruthy();
  });

  it('renders date range inputs', () => {
    render(<EventFilters filters={defaultFilters} onChange={() => {}} />);
    expect(screen.getByLabelText('Events from')).toBeTruthy();
    expect(screen.getByLabelText('Events to')).toBeTruthy();
  });

  it('calls onChange when date filter changes', () => {
    const onChange = vi.fn();
    render(<EventFilters filters={defaultFilters} onChange={onChange} />);
    const fromInput = screen.getByLabelText('Events from');
    fireEvent.change(fromInput, { target: { value: '2026-01-01T00:00' } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ GE_eventTime: '2026-01-01T00:00', offset: 0 }),
    );
  });
});
