// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { SubmodelNodeTree } from './SubmodelNodeTree';
import type { SubmodelNode } from '../types';

function makeLeaf(index: number): SubmodelNode {
  return {
    id: `leaf-${index}`,
    label: `Leaf ${index}`,
    path: `Root.Section${index}`,
    modelType: 'Property',
    value: `value-${index}`,
    children: [],
    meta: {
      qualifiers: {},
      required: index % 3 === 0,
      readOnly: false,
      validations: [],
    },
  };
}

function buildLargeRoot(count: number): SubmodelNode {
  return {
    id: 'root',
    label: 'Root',
    path: 'Root',
    modelType: 'Submodel',
    value: undefined,
    children: Array.from({ length: count }, (_, index) => makeLeaf(index + 1)),
    meta: {
      qualifiers: {},
      required: false,
      readOnly: false,
      validations: [],
    },
  };
}

describe('SubmodelNodeTree performance', () => {
  it('virtualizes large trees and avoids rendering all 1,000 nodes at once', () => {
    const root = buildLargeRoot(1000);

    const startedAt = performance.now();
    const { container } = render(
      <SubmodelNodeTree root={root} preferVirtualized virtualizeThreshold={120} />,
    );
    const elapsedMs = performance.now() - startedAt;

    // Sanity: virtualization path should mount a bounded number of rows.
    const renderedRows = container.querySelectorAll('[role="treeitem"]');
    expect(renderedRows.length).toBeLessThan(250);

    // Acceptance target: avoid obvious stalls during initial paint.
    expect(elapsedMs).toBeLessThan(1000);

    const treeRoot = container.querySelector('[role="tree"]');
    expect(treeRoot).toBeTruthy();
  });
});
