// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EventTypeBadge, ActionBadge } from '../components/EventTypeBadge';

describe('EventTypeBadge', () => {
  const eventTypes = [
    { type: 'ObjectEvent', label: 'Object' },
    { type: 'AggregationEvent', label: 'Aggregation' },
    { type: 'TransactionEvent', label: 'Transaction' },
    { type: 'TransformationEvent', label: 'Transformation' },
    { type: 'AssociationEvent', label: 'Association' },
  ] as const;

  it.each(eventTypes)('renders $label for $type', ({ type, label }) => {
    render(<EventTypeBadge type={type} />);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it('renders the raw type string for unknown types', () => {
    render(<EventTypeBadge type="CustomEvent" />);
    expect(screen.getByText('CustomEvent')).toBeTruthy();
  });
});

describe('ActionBadge', () => {
  it('renders ADD action', () => {
    render(<ActionBadge action="ADD" />);
    expect(screen.getByText('ADD')).toBeTruthy();
  });

  it('renders OBSERVE action', () => {
    render(<ActionBadge action="OBSERVE" />);
    expect(screen.getByText('OBSERVE')).toBeTruthy();
  });

  it('renders DELETE action', () => {
    render(<ActionBadge action="DELETE" />);
    expect(screen.getByText('DELETE')).toBeTruthy();
  });

  it('returns null for null action', () => {
    const { container } = render(<ActionBadge action={null} />);
    expect(container.innerHTML).toBe('');
  });
});
