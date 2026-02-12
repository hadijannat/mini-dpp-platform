// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import StandardsMapSection from '../StandardsMapSection';

describe('StandardsMapSection', () => {
  it('renders claim-level badges and evidence links', () => {
    render(<StandardsMapSection />);

    expect(screen.getAllByTestId('claim-level-implements').length).toBeGreaterThan(0);
    expect(screen.getByTestId('claim-level-aligned')).toBeTruthy();
    expect(screen.getByTestId('claim-level-roadmap')).toBeTruthy();

    expect(screen.getByText('AAS public router evidence')).toBeTruthy();
    expect(screen.getByText('Export service evidence')).toBeTruthy();
    expect(screen.getByText('Template router evidence')).toBeTruthy();
  });
});
