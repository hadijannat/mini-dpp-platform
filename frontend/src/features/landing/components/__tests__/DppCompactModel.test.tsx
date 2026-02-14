// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import DppCompactModel from '../DppCompactModel';

describe('DppCompactModel', () => {
  beforeEach(() => {
    cleanup();
  });

  it('renders AAS shell heading and all submodel tabs', () => {
    render(<DppCompactModel />);

    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain(
      'Asset Administration Shell (IEC 63278)',
    );
    expect(screen.getAllByRole('tab')).toHaveLength(7);
  });

  it('defaults to Digital Nameplate content and switches tabs', async () => {
    const user = userEvent.setup();

    render(<DppCompactModel />);

    expect(screen.getByRole('heading', { level: 3 }).textContent).toContain('Digital Nameplate');

    const carbonTab = screen.getByRole('tab', { name: /carbon/i });
    await user.click(carbonTab);

    expect(carbonTab.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('heading', { level: 3, name: /carbon footprint/i })).toBeTruthy();
    expect(screen.getByText('Public')).toBeTruthy();
  });

  it('switches to implementer mode metadata', () => {
    render(<DppCompactModel />);

    fireEvent.click(screen.getByRole('switch', { name: /implementer mode/i }));

    expect(screen.getByText('template_key')).toBeTruthy();
    expect(screen.getByText('semantic_id')).toBeTruthy();
    expect(screen.getByText('api_hint')).toBeTruthy();
  });

  it('has no obvious accessibility violations', async () => {
    const { container } = render(<DppCompactModel />);

    const a11y = await axe(container);

    expect(a11y.violations, JSON.stringify(a11y.violations, null, 2)).toHaveLength(0);
  });
});
