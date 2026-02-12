// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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
  beforeEach(() => {
    cleanup();
  });

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

  it('keeps user collapse state when nodes are rebuilt with stable ids', () => {
    const { rerender } = render(<DppOutlineTree nodes={buildTreeNodes()} />);

    const category = screen.getByRole('treeitem', { name: /Product Identity/i });
    category.focus();
    fireEvent.keyDown(category, { key: 'ArrowLeft' });

    expect(screen.queryByRole('treeitem', { name: /Nameplate/i })).toBeNull();

    rerender(<DppOutlineTree nodes={buildTreeNodes()} selectedId="category:identity" />);
    expect(screen.queryByRole('treeitem', { name: /Nameplate/i })).toBeNull();
  });

  it('expands selected node ancestors so active selection stays visible', () => {
    const { rerender } = render(<DppOutlineTree nodes={buildTreeNodes()} />);

    const category = screen.getByRole('treeitem', { name: /Product Identity/i });
    category.focus();
    fireEvent.keyDown(category, { key: 'ArrowLeft' });
    expect(screen.queryByRole('treeitem', { name: /Nameplate/i })).toBeNull();

    rerender(
      <DppOutlineTree
        nodes={buildTreeNodes()}
        selectedId="field:leaf"
      />,
    );

    expect(screen.getByRole('treeitem', { name: /ManufacturerName/i })).toBeTruthy();
  });

  it('renders virtualization branch when node count exceeds threshold', () => {
    const nodes: DppOutlineNode[] = Array.from({ length: 260 }, (_, index) => ({
      id: `field:${index}`,
      kind: 'field',
      label: `Node ${index + 1}`,
      path: `Node.${index + 1}`,
      children: [],
    }));

    const { container } = render(
      <DppOutlineTree
        nodes={nodes}
        virtualizeThreshold={10}
      />,
    );

    expect(screen.getByRole('tree')).toBeTruthy();
    expect(container.querySelector('div.relative[style*="height"]')).toBeTruthy();
  });
});
