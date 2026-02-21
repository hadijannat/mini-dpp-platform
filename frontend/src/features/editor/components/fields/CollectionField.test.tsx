// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { useForm } from 'react-hook-form';
import { CollectionField } from './CollectionField';
import type { DefinitionNode } from '../../types/definition';

/**
 * Wrapper that provides a react-hook-form context and renders CollectionField
 * with a `renderNode` callback that stamps each child's idShort into the DOM.
 */
function RenderCollection({ children }: { children: DefinitionNode[] }) {
  const form = useForm<Record<string, unknown>>({ defaultValues: {} });

  return (
    <CollectionField
      name="root"
      control={form.control}
      node={{
        modelType: 'SubmodelElementCollection',
        idShort: 'TestCollection',
        children,
      }}
      depth={0}
      renderNode={({ node }) => (
        <span data-testid={`child-${node.idShort}`}>{node.idShort}</span>
      )}
    />
  );
}

describe('CollectionField sorting', () => {
  afterEach(() => {
    cleanup();
  });

  it('sorts children by order ascending', () => {
    const children: DefinitionNode[] = [
      { modelType: 'Property', idShort: 'Gamma', order: 3 },
      { modelType: 'Property', idShort: 'Alpha', order: 1 },
      { modelType: 'Property', idShort: 'Beta', order: 2 },
    ];
    render(<RenderCollection>{children}</RenderCollection>);

    const items = screen.getAllByTestId(/^child-/);
    expect(items.map((el) => el.textContent)).toEqual(['Alpha', 'Beta', 'Gamma']);
  });

  it('sorts children alphabetically by idShort when order is absent', () => {
    const children: DefinitionNode[] = [
      { modelType: 'Property', idShort: 'Zebra' },
      { modelType: 'Property', idShort: 'Apple' },
      { modelType: 'Property', idShort: 'Mango' },
    ];
    render(<RenderCollection>{children}</RenderCollection>);

    const items = screen.getAllByTestId(/^child-/);
    expect(items.map((el) => el.textContent)).toEqual(['Apple', 'Mango', 'Zebra']);
  });

  it('places ordered children before unordered, then alphabetical tiebreak', () => {
    const children: DefinitionNode[] = [
      { modelType: 'Property', idShort: 'Zulu' },          // no order → MAX_SAFE_INTEGER
      { modelType: 'Property', idShort: 'Bravo', order: 2 },
      { modelType: 'Property', idShort: 'Alpha' },          // no order → MAX_SAFE_INTEGER
      { modelType: 'Property', idShort: 'Charlie', order: 1 },
    ];
    render(<RenderCollection>{children}</RenderCollection>);

    const items = screen.getAllByTestId(/^child-/);
    // order=1 first, order=2 second, then unordered alphabetically
    expect(items.map((el) => el.textContent)).toEqual([
      'Charlie', 'Bravo', 'Alpha', 'Zulu',
    ]);
  });
});
