import { describe, expect, it } from 'vitest';
import type { DppOutlineNode } from '../../types';
import { filterOutlineNodes } from '../filterOutline';

function buildNodes(): DppOutlineNode[] {
  return [
    {
      id: 'category:identity',
      kind: 'category',
      label: 'Product Identity',
      path: 'identity',
      searchableText: 'identity',
      children: [
        {
          id: 'submodel:nameplate',
          kind: 'submodel',
          label: 'Nameplate',
          path: 'submodel.nameplate',
          meta: {
            templateKey: 'digital-nameplate',
          },
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
      ],
    },
  ];
}

describe('filterOutlineNodes', () => {
  it('returns matching descendants while keeping ancestors', () => {
    const filtered = filterOutlineNodes(buildNodes(), 'ManufacturerName');
    expect(filtered).toHaveLength(1);
    expect(filtered[0].label).toBe('Product Identity');
    expect(filtered[0].children).toHaveLength(1);
    expect(filtered[0].children[0].children).toHaveLength(1);
    expect(filtered[0].children[0].children[0].label).toBe('ManufacturerName');
  });

  it('matches metadata fields like template key', () => {
    const filtered = filterOutlineNodes(buildNodes(), 'digital-nameplate');
    expect(filtered).toHaveLength(1);
    expect(filtered[0].children[0].label).toBe('Nameplate');
  });

  it('returns empty array when nothing matches', () => {
    const filtered = filterOutlineNodes(buildNodes(), 'no-such-node');
    expect(filtered).toEqual([]);
  });
});
