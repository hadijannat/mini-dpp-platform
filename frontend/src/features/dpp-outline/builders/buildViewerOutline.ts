import type { ClassifiedNode, ESPRCategory } from '@/features/viewer/utils/esprCategories';
import { buildViewerOutlineKey } from '@/features/viewer/utils/outlineKey';
import { completionFromChildren, createOutlineNodeId, type DppOutlineNode } from '../types';

type BuildViewerOutlineParams = {
  categories: ESPRCategory[];
  classified: Record<string, ClassifiedNode[]>;
};

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
  return false;
}

export function buildViewerOutline({
  categories,
  classified,
}: BuildViewerOutlineParams): DppOutlineNode[] {
  const nodes: DppOutlineNode[] = [];

  for (const category of categories) {
    const elements = classified[category.id] ?? [];
    if (elements.length === 0) continue;

    const submodelMap = new Map<string, DppOutlineNode>();

    elements.forEach((element, index) => {
      const submodelKey = element.submodelIdShort;
      if (!submodelMap.has(submodelKey)) {
        submodelMap.set(submodelKey, {
          id: createOutlineNodeId('submodel', `viewer.${category.id}.${submodelKey}`),
          kind: 'submodel',
          label: submodelKey,
          path: `viewer.${category.id}.${submodelKey}`,
          searchableText: `${category.label} ${submodelKey}`,
          meta: {
            categoryId: category.id,
            categoryLabel: category.label,
          },
          target: {
            type: 'dom',
            path: category.id,
          },
          children: [],
        });
      }

      const key = buildViewerOutlineKey(element, index);
      const fieldNode: DppOutlineNode = {
        id: createOutlineNodeId('field', `viewer.${category.id}.${key}`),
        kind: 'field',
        label: element.label,
        path: key,
        idShort: element.label,
        semanticId: element.semanticId,
        searchableText: `${element.label} ${element.path} ${element.submodelIdShort}`,
        status: {
          completion: isEmptyValue(element.value) ? 'empty' : 'complete',
        },
        target: {
          type: 'dom',
          path: key,
        },
        meta: {
          categoryId: category.id,
          categoryLabel: category.label,
          outlineKey: key,
          submodelId: element.submodelIdShort,
        },
        children: [],
      };

      submodelMap.get(submodelKey)!.children.push(fieldNode);
    });

    const submodels = Array.from(submodelMap.values()).map((submodel) => ({
      ...submodel,
      status: {
        completion: completionFromChildren(submodel.children),
      },
    }));

    nodes.push({
      id: createOutlineNodeId('category', `viewer.${category.id}`),
      kind: 'category',
      label: category.label,
      path: category.id,
      searchableText: `${category.label} ${category.description}`,
      target: {
        type: 'dom',
        path: category.id,
      },
      meta: {
        categoryId: category.id,
        categoryLabel: category.label,
      },
      status: {
        completion: completionFromChildren(submodels),
      },
      children: submodels,
    });
  }

  return nodes;
}
