// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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
  afterEach(() => {
    cleanup();
  });

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

  it('resets interaction values when step changes', async () => {
    const onSubmit = vi.fn();
    const onHint = vi.fn();
    const nextStep: CirpassLabStep = {
      ...step,
      id: 'access-passport',
      level: 'access',
      title: 'Access passport',
      interaction: {
        kind: 'form',
        submit_label: 'Validate access',
        fields: [
          {
            name: 'route',
            label: 'Route',
            type: 'text',
            required: true,
            test_id: 'cirpass-access-route',
          },
        ],
        options: [],
      },
    };

    const { rerender } = render(
      <StepInteractionRenderer
        step={step}
        objective="Create objective"
        derivedHint="hint"
        onSubmit={onSubmit}
        onHint={onHint}
      />,
    );

    fireEvent.change(screen.getByTestId('cirpass-create-identifier'), {
      target: { value: 'did:web:stale' },
    });

    rerender(
      <StepInteractionRenderer
        step={nextStep}
        objective="Access objective"
        derivedHint="hint"
        onSubmit={onSubmit}
        onHint={onHint}
      />,
    );

    expect(screen.queryByTestId('cirpass-create-identifier')).toBeNull();
    const routeInput = screen.getByTestId('cirpass-access-route') as HTMLInputElement;
    expect(routeInput.value).toBe('');

    fireEvent.change(routeInput, { target: { value: 'consumer' } });
    fireEvent.submit(screen.getByTestId('cirpass-level-submit').closest('form')!);

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
    expect(onSubmit.mock.calls[0][0]).toEqual({
      route: 'consumer',
    });
    expect(onHint).not.toHaveBeenCalled();
  });
});
