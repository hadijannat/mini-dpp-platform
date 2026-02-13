// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import FAQSection from '../FAQSection';

describe('FAQSection', () => {
  it('renders FAQ heading and key questions', () => {
    render(<FAQSection />);

    expect(
      screen.getByRole('heading', { name: /Common questions from compliance and engineering teams/i }),
    ).toBeTruthy();
    expect(screen.getByText('What is a Digital Product Passport under ESPR?')).toBeTruthy();
    expect(screen.getByText('Is this implementation aligned with AAS and IDTA DPP4.0?')).toBeTruthy();
    expect(screen.getByText('Can I self-host the platform?')).toBeTruthy();
  });
});
