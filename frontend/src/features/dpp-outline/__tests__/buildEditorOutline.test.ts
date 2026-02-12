import { describe, expect, it } from 'vitest';
import type { SubmodelHealth, SubmodelNode } from '@/features/submodels/types';
import { buildEditorOutline } from '../builders/buildEditorOutline';

function fieldMeta(required = false) {
  return {
    semanticId: undefined,
    qualifiers: {},
    cardinality: required ? 'One' : undefined,
    required,
    readOnly: false,
    validations: [],
  };
}

function buildRootNode(): SubmodelNode {
  return {
    id: 'sm-1',
    label: 'Nameplate',
    path: 'Nameplate',
    modelType: 'Submodel',
    value: undefined,
    meta: fieldMeta(false),
    children: [
      {
        id: 'section-1',
        label: 'ManufacturerData',
        path: 'Nameplate.ManufacturerData',
        modelType: 'SubmodelElementCollection',
        value: undefined,
        meta: fieldMeta(false),
        children: [
          {
            id: 'field-1',
            label: 'ManufacturerName',
            path: 'Nameplate.ManufacturerData.ManufacturerName',
            modelType: 'Property',
            value: 'ACME',
            meta: fieldMeta(true),
            children: [],
          },
          {
            id: 'field-2',
            label: 'ProductCode',
            path: 'Nameplate.ManufacturerData.ProductCode',
            modelType: 'Property',
            value: '',
            meta: fieldMeta(true),
            children: [],
          },
        ],
      },
    ],
  };
}

describe('buildEditorOutline', () => {
  it('builds category -> submodel -> section -> field nodes with route targets', () => {
    const health: SubmodelHealth = {
      totalRequired: 2,
      completedRequired: 1,
      validationSignals: 3,
      leafCount: 2,
    };

    const nodes = buildEditorOutline({
      dppId: 'dpp-1',
      submodels: [
        {
          submodelId: 'sm-1',
          templateKey: 'digital-nameplate',
          submodelLabel: 'Nameplate',
          categoryId: 'identity',
          categoryLabel: 'Product Identity',
          completionPercent: 50,
          risk: 'medium',
          health,
          rootNode: buildRootNode(),
          editHref: '/console/dpps/dpp-1/edit/digital-nameplate',
          semanticId: 'urn:semantic:nameplate',
        },
      ],
    });

    expect(nodes).toHaveLength(1);
    expect(nodes[0].label).toBe('Product Identity');

    const submodel = nodes[0].children[0];
    expect(submodel.kind).toBe('submodel');
    expect(submodel.status?.completion).toBe('partial');
    expect(submodel.status?.requiredTotal).toBe(2);
    expect(submodel.status?.requiredCompleted).toBe(1);
    expect(submodel.status?.warnings).toBe(3);
    expect(submodel.target).toEqual({
      type: 'route',
      href: '/console/dpps/dpp-1/edit/digital-nameplate',
      query: { submodel_id: 'sm-1' },
    });

    const section = submodel.children[0];
    expect(section.kind).toBe('section');
    expect(section.path).toBe('ManufacturerData');

    const field = section.children[0];
    expect(field.kind).toBe('field');
    expect(field.path).toBe('ManufacturerData.ManufacturerName');
    expect(field.target).toEqual({
      type: 'route',
      href: '/console/dpps/dpp-1/edit/digital-nameplate',
      query: {
        submodel_id: 'sm-1',
        focus_path: 'ManufacturerData.ManufacturerName',
        focus_id_short: 'ManufacturerName',
      },
    });
  });
});
