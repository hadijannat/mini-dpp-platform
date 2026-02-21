// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSubmodelForm } from './useSubmodelForm';
import type { TemplateDefinition } from '../types/definition';

const defA: TemplateDefinition = {
  submodel: {
    elements: [
      { modelType: 'Property', idShort: 'name', valueType: 'xs:string' },
    ],
  },
};

const defB: TemplateDefinition = {
  submodel: {
    elements: [
      { modelType: 'Property', idShort: 'title', valueType: 'xs:string' },
    ],
  },
};

describe('useSubmodelForm', () => {
  it('initialises form with provided data', () => {
    const initialData = { name: 'Widget' };
    const { result } = renderHook(() => useSubmodelForm(defA, undefined, initialData));

    expect(result.current.form.getValues()).toEqual(
      expect.objectContaining({ name: 'Widget' }),
    );
  });

  it('resets form values when definition changes', async () => {
    const dataA = { name: 'Widget' };
    const dataB = { title: 'Gadget' };

    const { result, rerender } = renderHook(
      ({ def, data }: { def: TemplateDefinition; data: Record<string, unknown> }) =>
        useSubmodelForm(def, undefined, data),
      { initialProps: { def: defA, data: dataA as Record<string, unknown> } },
    );

    expect(result.current.form.getValues()).toEqual(
      expect.objectContaining({ name: 'Widget' }),
    );

    // Switch to a different definition + data
    await act(async () => {
      rerender({ def: defB, data: dataB as Record<string, unknown> });
    });

    expect(result.current.form.getValues()).toEqual(
      expect.objectContaining({ title: 'Gadget' }),
    );
    // Stale value from prior definition should not persist
    expect(result.current.form.getValues().name).toBeUndefined();
  });

  it('resets form values when initialData changes for the same definition', async () => {
    const dataV1 = { name: 'Version 1' };
    const dataV2 = { name: 'Version 2' };

    const { result, rerender } = renderHook(
      ({ data }) => useSubmodelForm(defA, undefined, data),
      { initialProps: { data: dataV1 } },
    );

    expect(result.current.form.getValues('name')).toBe('Version 1');

    await act(async () => {
      rerender({ data: dataV2 });
    });

    expect(result.current.form.getValues('name')).toBe('Version 2');
  });

  it('does not reset when initialData identity changes with the same semantic content', async () => {
    const dataV1 = { name: 'Stable' };
    const dataV1Clone = { name: 'Stable' };

    const { result, rerender } = renderHook(
      ({ data }) => useSubmodelForm(defA, undefined, data),
      { initialProps: { data: dataV1 } },
    );

    await act(async () => {
      result.current.form.setValue('name', 'Edited');
    });
    expect(result.current.form.getValues('name')).toBe('Edited');

    await act(async () => {
      rerender({ data: dataV1Clone });
    });

    expect(result.current.form.getValues('name')).toBe('Edited');
  });
});
