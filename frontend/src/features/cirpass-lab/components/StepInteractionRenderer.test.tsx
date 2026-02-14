// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import StepInteractionRenderer from './StepInteractionRenderer';
import type { CirpassLabStep } from '../schema/storySchema';

const step: CirpassLabStep = {
  id: 'create-passport',
  level: 'create',
  title: 'Create passport',
  actor: 'Manufacturer',
  intent: 'Create payload',
  explanation_md: 'Create payload',
  interaction: {
    kind: 'form',
    submit_label: 'Validate & Continue',
    fields: [
      {
        name: 'identifier',
        label: 'Identifier',
        type: 'text',
        required: true,
        test_id: 'cirpass-create-identifier',
      },
      {
        name: 'carbonFootprint',
        label: 'Carbon footprint',
        type: 'number',
        required: true,
        validation: { gt: 0 },
        test_id: 'cirpass-create-carbon',
      },
    ],
    options: [],
  },
  checks: [],
  variants: ['happy'],
};

describe('StepInteractionRenderer', () => {
  it('renders manifest fields and submits normalized payload', async () => {
    const onSubmit = vi.fn();
    const onHint = vi.fn();

    render(
      <StepInteractionRenderer
        step={step}
        objective="Create objective"
        derivedHint="hint"
        onSubmit={onSubmit}
        onHint={onHint}
      />,
    );

    fireEvent.change(screen.getByTestId('cirpass-create-identifier'), {
      target: { value: 'did:web:demo' },
    });
    fireEvent.change(screen.getByTestId('cirpass-create-carbon'), {
      target: { value: '12.5' },
    });
    fireEvent.submit(screen.getByTestId('cirpass-level-submit').closest('form')!);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    expect(onSubmit.mock.calls[0][0]).toEqual({
      identifier: 'did:web:demo',
      carbonFootprint: 12.5,
    });

    fireEvent.click(screen.getByTestId('cirpass-level-hint'));
    expect(onHint).toHaveBeenCalledTimes(1);
  });
});
