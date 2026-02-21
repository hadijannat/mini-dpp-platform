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
        hint: 'Use a globally unique identifier.',
        test_id: 'cirpass-create-identifier',
      },
      {
        name: 'carbonFootprint',
        label: 'Carbon footprint',
        type: 'number',
        required: true,
        hint: 'Use a positive value in kg CO2e.',
        validation: { gt: 0 },
        test_id: 'cirpass-create-carbon',
      },
    ],
    options: [],
  },
  api: {
    method: 'POST',
    path: '/api/v1/tenants/{tenant}/dpps',
    auth: 'user',
    expected_status: 201,
    request_example: {
      identifier: 'did:web:dpp.eu:product:demo-bike',
      carbonFootprint: 14.2,
      ignoredField: 'not-used',
    },
  },
  checks: [],
  variants: ['happy'],
};

function mockClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  });
  return writeText;
}

describe('StepInteractionRenderer', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
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

  it('uses request example values and copies current payload JSON', async () => {
    const writeText = mockClipboard();

    render(
      <StepInteractionRenderer
        step={step}
        objective="Create objective"
        derivedHint="hint"
        onSubmit={vi.fn()}
        onHint={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId('cirpass-level-use-example'));

    expect((screen.getByTestId('cirpass-create-identifier') as HTMLInputElement).value).toBe(
      'did:web:dpp.eu:product:demo-bike',
    );
    expect((screen.getByTestId('cirpass-create-carbon') as HTMLInputElement).value).toBe('14.2');

    fireEvent.click(screen.getByTestId('cirpass-level-copy-json'));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledTimes(1);
    });
    const copiedJson = writeText.mock.calls[0][0] as string;
    const copiedPayload = JSON.parse(copiedJson) as Record<string, unknown>;
    expect(copiedPayload).toEqual({
      identifier: 'did:web:dpp.eu:product:demo-bike',
      carbonFootprint: 14.2,
    });
    expect(screen.getByTestId('cirpass-level-copy-json').textContent).toContain('Copied');
  });

  it('shows an error summary, focuses it on invalid submit, and links to invalid fields', async () => {
    const onSubmit = vi.fn();

    render(
      <StepInteractionRenderer
        step={step}
        objective="Create objective"
        derivedHint="hint"
        onSubmit={onSubmit}
        onHint={vi.fn()}
      />,
    );

    fireEvent.submit(screen.getByTestId('cirpass-level-submit').closest('form')!);

    const summary = await screen.findByTestId('cirpass-error-summary');
    expect(summary.getAttribute('role')).toBe('alert');
    expect(summary.getAttribute('aria-live')).toBe('assertive');

    await waitFor(() => {
      expect(document.activeElement).toBe(summary);
    });

    expect(onSubmit).not.toHaveBeenCalled();

    const identifierInput = screen.getByTestId('cirpass-create-identifier');
    expect(identifierInput.getAttribute('aria-invalid')).toBe('true');
    const describedBy = identifierInput.getAttribute('aria-describedby') ?? '';
    expect(describedBy).toContain('create-passport-identifier-hint');
    expect(describedBy).toContain('create-passport-identifier-error');

    fireEvent.click(screen.getByTestId('cirpass-error-link-identifier'));
    expect(document.activeElement).toBe(identifierInput);
  });

  it('renders inline checkbox errors with aria linkage', async () => {
    const checkboxStep: CirpassLabStep = {
      ...step,
      id: 'access-passport',
      level: 'access',
      interaction: {
        kind: 'form',
        submit_label: 'Validate access',
        fields: [
          {
            name: 'policyAccepted',
            label: 'Policy approved',
            type: 'checkbox',
            required: true,
            hint: 'Check this box to proceed.',
            validation: {
              equals: true,
            },
            test_id: 'cirpass-access-policy',
          },
        ],
        options: [],
      },
      api: undefined,
    };

    render(
      <StepInteractionRenderer
        step={checkboxStep}
        objective="Access objective"
        derivedHint="hint"
        onSubmit={vi.fn()}
        onHint={vi.fn()}
      />,
    );

    fireEvent.submit(screen.getByTestId('cirpass-level-submit').closest('form')!);

    await screen.findByTestId('cirpass-error-summary');

    const checkbox = screen.getByTestId('cirpass-access-policy');
    expect(checkbox.getAttribute('aria-invalid')).toBe('true');
    const describedBy = checkbox.getAttribute('aria-describedby') ?? '';
    expect(describedBy).toContain('access-passport-policyAccepted-hint');
    expect(describedBy).toContain('access-passport-policyAccepted-error');

    const errorNode = document.getElementById('access-passport-policyAccepted-error');
    expect(errorNode?.textContent ?? '').toContain('Policy approved');
  });
});
