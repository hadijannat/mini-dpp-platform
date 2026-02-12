// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { DppOutlineTree } from '../DppOutlineTree';
import type { DppOutlineNode } from '../../types';

function buildTreeNodes(): DppOutlineNode[] {
  return [
    {
      id: 'category:identity',
      kind: 'category',
      label: 'Product Identity',
      path: 'identity',
      children: [
        {
          id: 'submodel:nameplate',
          kind: 'submodel',
          label: 'Nameplate',
          path: 'submodel.nameplate',
          children: [
            {
              id: 'section:manufacturer',
              kind: 'section',
              label: 'ManufacturerData',
              path: 'ManufacturerData',
              children: [
                {
                  id: 'section:nested',
                  kind: 'section',
                  label: 'NestedSection',
                  path: 'ManufacturerData.NestedSection',
                  children: [
                    {
                      id: 'field:leaf',
                      kind: 'field',
                      label: 'ManufacturerName',
                      path: 'ManufacturerData.NestedSection.ManufacturerName',
                      children: [],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    },
  ];
}

describe('DppOutlineTree', () => {
  it('supports keyboard expand/collapse and selection', () => {
    const onSelectNode = vi.fn();
    render(<DppOutlineTree nodes={buildTreeNodes()} onSelectNode={onSelectNode} />);

    expect(screen.queryByRole('treeitem', { name: /ManufacturerName/i })).toBeNull();

    const manufacturerSection = screen.getByRole('treeitem', { name: /ManufacturerData/i });
    manufacturerSection.focus();
    fireEvent.keyDown(manufacturerSection, { key: 'ArrowRight' });

    const nestedSection = screen.getByRole('treeitem', { name: /NestedSection/i });
    nestedSection.focus();
    fireEvent.keyDown(nestedSection, { key: 'ArrowRight' });

    expect(screen.getByRole('treeitem', { name: /ManufacturerName/i })).toBeTruthy();

    fireEvent.keyDown(nestedSection, { key: 'Enter' });
    expect(onSelectNode).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'section:nested',
        path: 'ManufacturerData.NestedSection',
      }),
    );

    fireEvent.keyDown(nestedSection, { key: 'ArrowLeft' });
    expect(screen.queryByRole('treeitem', { name: /ManufacturerName/i })).toBeNull();
  });
});
