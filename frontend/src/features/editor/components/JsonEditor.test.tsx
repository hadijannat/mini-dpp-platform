// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { JsonEditor } from './JsonEditor';
import type { UISchema } from '../types/uiSchema';

vi.mock('@uiw/react-codemirror', () => ({
  default: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <textarea
      aria-label="Submodel JSON editor"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

afterEach(() => {
  cleanup();
});

describe('JsonEditor', () => {
  it('emits root issue for invalid JSON', async () => {
    const onIssuesChange = vi.fn();

    render(<JsonEditor value="{" onChange={vi.fn()} onIssuesChange={onIssuesChange} />);

    await waitFor(() => {
      const issues = onIssuesChange.mock.calls.at(-1)?.[0] as Array<{ path: string }> | undefined;
      expect(issues?.[0]?.path).toBe('root');
    });
  });

  it('emits schema issues for invalid payload shape', async () => {
    const schema: UISchema = {
      type: 'object',
      required: ['ManufacturerName'],
      properties: {
        ManufacturerName: { type: 'string' },
      },
    };
    const onIssuesChange = vi.fn();

    render(<JsonEditor value="{}" onChange={vi.fn()} schema={schema} onIssuesChange={onIssuesChange} />);

    await waitFor(() => {
      const issues = onIssuesChange.mock.calls.at(-1)?.[0] as Array<{ path: string }> | undefined;
      expect(issues?.some((issue) => issue.path === 'ManufacturerName')).toBe(true);
    });
  });

  it('emits no issues for valid JSON and keeps editable onChange behavior', async () => {
    const schema: UISchema = {
      type: 'object',
      required: ['ManufacturerName'],
      properties: {
        ManufacturerName: { type: 'string' },
      },
    };
    const onIssuesChange = vi.fn();
    const onChange = vi.fn();

    render(
      <JsonEditor
        value={JSON.stringify({ ManufacturerName: 'ACME' })}
        onChange={onChange}
        schema={schema}
        onIssuesChange={onIssuesChange}
      />,
    );

    await waitFor(() => {
      const issues = onIssuesChange.mock.calls.at(-1)?.[0] as Array<{ path: string }> | undefined;
      expect(issues).toEqual([]);
    });

    fireEvent.change(screen.getByLabelText(/Submodel JSON editor/i), {
      target: { value: JSON.stringify({ ManufacturerName: 'ACME 2' }) },
    });

    expect(onChange).toHaveBeenCalled();
  });
});
