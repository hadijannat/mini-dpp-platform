import { describe, expect, it } from 'vitest';
import { ESPR_CATEGORIES } from '@/features/viewer/utils/esprCategories';
import { buildViewerOutlineKey } from '@/features/viewer/utils/outlineKey';
import { buildViewerOutline } from '../builders/buildViewerOutline';

describe('buildViewerOutline', () => {
  it('groups viewer nodes as category -> submodel -> field with stable dom targets', () => {
    const identityNode = {
      submodelIdShort: 'Nameplate',
      path: 'Nameplate.ManufacturerName',
      label: 'ManufacturerName',
      value: 'ACME',
      modelType: 'Property',
    };
    const environmentalNode = {
      submodelIdShort: 'CarbonFootprint',
      path: 'CarbonFootprint.TotalCO2',
      label: 'TotalCO2',
      value: '',
      modelType: 'Property',
    };

    const classified: Record<string, typeof identityNode[]> = {
      identity: [identityNode],
      environmental: [environmentalNode],
    };

    const nodes = buildViewerOutline({
      categories: ESPR_CATEGORIES,
      classified,
    });

    expect(nodes.map((node) => node.path)).toEqual(
      expect.arrayContaining(['identity', 'environmental']),
    );

    const identity = nodes.find((node) => node.path === 'identity');
    expect(identity?.children[0].label).toBe('Nameplate');
    const identityField = identity?.children[0].children[0];
    expect(identityField?.status?.completion).toBe('complete');
    expect(identityField?.target).toEqual({
      type: 'dom',
      path: buildViewerOutlineKey(identityNode, 0),
    });

    const environmental = nodes.find((node) => node.path === 'environmental');
    const environmentalField = environmental?.children[0].children[0];
    expect(environmentalField?.status?.completion).toBe('empty');
  });
});
