// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FieldWrapper } from './FieldWrapper';

describe('FieldWrapper', () => {
  it('renders label and children', () => {
    render(
      <FieldWrapper label="Field Name">
        <input data-testid="child-input" />
      </FieldWrapper>,
    );
    expect(screen.getByText('Field Name')).toBeTruthy();
    expect(screen.getByTestId('child-input')).toBeTruthy();
  });

  it('shows required indicator', () => {
    render(
      <FieldWrapper label="Required Field" required>
        <span>content</span>
      </FieldWrapper>,
    );
    expect(screen.getByText('*')).toBeTruthy();
  });

  it('does not show required indicator when not required', () => {
    const { container } = render(
      <FieldWrapper label="Optional">
        <span>content</span>
      </FieldWrapper>,
    );
    expect(container.querySelector('.text-destructive')).toBeNull();
  });

  it('renders description info icon', () => {
    const { container } = render(
      <FieldWrapper label="Field" description="Some helpful text">
        <span>content</span>
      </FieldWrapper>,
    );
    // Description is now inside a Tooltip (shown on hover); the info icon is always rendered
    expect(container.querySelector('svg.lucide-info')).toBeTruthy();
  });

  it('does not render info icon when no description', () => {
    const { container } = render(
      <FieldWrapper label="Field">
        <span>content</span>
      </FieldWrapper>,
    );
    expect(container.querySelector('svg.lucide-info')).toBeNull();
  });

  it('renders unit in label', () => {
    render(
      <FieldWrapper label="Weight" unit="kg">
        <span>content</span>
      </FieldWrapper>,
    );
    expect(screen.getByText('(kg)')).toBeTruthy();
  });

  it('renders "Learn more" link', () => {
    render(
      <FieldWrapper label="Field" formUrl="https://example.com/docs">
        <span>content</span>
      </FieldWrapper>,
    );
    const link = screen.getByText('Learn more');
    expect(link).toBeTruthy();
    expect((link as HTMLAnchorElement).href).toBe('https://example.com/docs');
    expect((link as HTMLAnchorElement).target).toBe('_blank');
  });

  it('renders error message', () => {
    render(
      <FieldWrapper label="Field" error="This field is required">
        <span>content</span>
      </FieldWrapper>,
    );
    expect(screen.getByText('This field is required')).toBeTruthy();
  });

  it('does not render optional elements when not provided', () => {
    const { container } = render(
      <FieldWrapper label="Simple">
        <span>content</span>
      </FieldWrapper>,
    );
    // No description (no info icon), no error, no links
    expect(container.querySelectorAll('a')).toHaveLength(0);
    expect(container.querySelector('svg.lucide-info')).toBeNull();
    expect(container.querySelector('.text-destructive')).toBeNull();
  });
});
