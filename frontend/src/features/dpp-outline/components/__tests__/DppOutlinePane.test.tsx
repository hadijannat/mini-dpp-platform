// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { DppOutlinePane } from '../DppOutlinePane';
import type { DppOutlineNode } from '../../types';

const nodes: DppOutlineNode[] = [
  {
    id: 'category:identity',
    kind: 'category',
    label: 'Product Identity',
    path: 'identity',
    children: [
      {
        id: 'field:manufacturer',
        kind: 'field',
        label: 'ManufacturerName',
        path: 'ManufacturerData.ManufacturerName',
        children: [],
      },
    ],
  },
];

describe('DppOutlinePane', () => {
  beforeEach(() => {
    cleanup();
  });

  it('shows empty-state message when search has no results', () => {
    render(<DppOutlinePane context="viewer" nodes={nodes} />);

    fireEvent.change(screen.getByLabelText(/Search structure outline/i), {
      target: { value: 'does-not-exist' },
    });

    expect(
      screen.getByText(/No outline nodes match the current filter/i),
    ).toBeTruthy();
  });

  it('shows matching nodes when search query matches', () => {
    render(<DppOutlinePane context="viewer" nodes={nodes} />);

    fireEvent.change(screen.getByLabelText(/Search structure outline/i), {
      target: { value: 'manufacturer' },
    });

    expect(screen.getByRole('treeitem', { name: /ManufacturerName/i })).toBeTruthy();
  });
});
