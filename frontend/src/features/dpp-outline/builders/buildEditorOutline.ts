import type { SubmodelHealth, SubmodelNode } from '@/features/submodels/types';
import {
  completionFromChildren,
  createOutlineNodeId,
  type DppOutlineCompletion,
  type DppOutlineNode,
  type DppOutlineRisk,
} from '../types';

export type EditorOutlineSubmodel = {
  submodelId: string;
  templateKey: string | null;
  submodelLabel: string;
  categoryId: string;
  categoryLabel: string;
  completionPercent: number | null;
  risk: 'low' | 'medium' | 'high';
  health: SubmodelHealth;
  rootNode: SubmodelNode;
  editHref: string | null;
  semanticId?: string | null;
};

type BuildEditorOutlineParams = {
  dppId: string;
  submodels: EditorOutlineSubmodel[];
};

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
  return false;
}

function normalizePath(path: string): string {
  return path.replace(/\[(\d+)\]/g, '.$1').replace(/^\./, '');
}

function inferCompletion(node: SubmodelNode): DppOutlineCompletion {
  if (node.children.length === 0) {
    return isEmptyValue(node.value) ? 'empty' : 'complete';
  }

  const childStates = node.children.map((child) => inferCompletion(child));
  if (childStates.every((state) => state === 'complete')) return 'complete';
  if (childStates.every((state) => state === 'empty')) return 'empty';
  return 'partial';
}

function buildFieldChildren(params: {
  node: SubmodelNode;
  parentPath: string;
  editHref: string | null;
  submodelId: string;
}): DppOutlineNode {
  const { node, parentPath, editHref, submodelId } = params;
  const currentPath = normalizePath(parentPath ? `${parentPath}.${node.label}` : node.label);
  const completion = inferCompletion(node);
  const children = node.children.map((child) =>
    buildFieldChildren({
      node: child,
      parentPath: currentPath,
      editHref,
      submodelId,
    }),
  );

  const target =
    editHref === null
      ? undefined
      : {
          type: 'route' as const,
          href: editHref,
          query: {
            submodel_id: submodelId,
            focus_path: currentPath,
            focus_id_short: node.label,
          },
        };

  return {
    id: createOutlineNodeId(
      node.children.length > 0 ? 'section' : 'field',
      `submodel.${submodelId}.${currentPath}`,
    ),
    kind: node.children.length > 0 ? 'section' : 'field',
    label: node.label,
    path: currentPath,
    idShort: node.label,
    semanticId: node.meta.semanticId,
    searchableText: `${node.label} ${currentPath} ${node.meta.semanticId ?? ''}`,
    status: {
      completion,
      required: node.meta.required,
    },
    target,
    children,
  };
}

function deriveSubmodelCompletion(health: SubmodelHealth): DppOutlineCompletion {
  if (health.totalRequired === 0) return 'complete';
  if (health.completedRequired === 0) return 'empty';
  if (health.completedRequired >= health.totalRequired) return 'complete';
  return 'partial';
}

function riskToOutlineRisk(risk: 'low' | 'medium' | 'high'): DppOutlineRisk {
  return risk;
}

export function buildEditorOutline({ dppId, submodels }: BuildEditorOutlineParams): DppOutlineNode[] {
  const categoryMap = new Map<string, DppOutlineNode>();

  for (const entry of submodels) {
    if (!categoryMap.has(entry.categoryId)) {
      const categoryNode: DppOutlineNode = {
        id: createOutlineNodeId('category', `category.${entry.categoryId}`),
        kind: 'category',
        label: entry.categoryLabel,
        path: `category.${entry.categoryId}`,
        searchableText: `${entry.categoryLabel} ${entry.categoryId}`,
        children: [],
      };
      categoryMap.set(entry.categoryId, categoryNode);
    }

    const categoryNode = categoryMap.get(entry.categoryId)!;
    const editHref = entry.editHref ?? (entry.templateKey ? `/console/dpps/${dppId}/edit/${entry.templateKey}` : null);

    const sectionChildren = entry.rootNode.children.map((child) =>
      buildFieldChildren({
        node: child,
        parentPath: '',
        editHref,
        submodelId: entry.submodelId,
      }),
    );

    const submodelNode: DppOutlineNode = {
      id: createOutlineNodeId('submodel', `submodel.${entry.submodelId}`),
      kind: 'submodel',
      label: entry.submodelLabel,
      path: `submodel.${entry.submodelId}`,
      semanticId: entry.semanticId ?? undefined,
      searchableText: `${entry.submodelLabel} ${entry.templateKey ?? ''} ${entry.semanticId ?? ''}`,
      status: {
        completion: deriveSubmodelCompletion(entry.health),
        requiredTotal: entry.health.totalRequired,
        requiredCompleted: entry.health.completedRequired,
        warnings: entry.health.validationSignals,
        risk: riskToOutlineRisk(entry.risk),
      },
      target:
        editHref === null
          ? undefined
          : {
              type: 'route',
              href: editHref,
              query: {
                submodel_id: entry.submodelId,
              },
            },
      meta: {
        templateKey: entry.templateKey ?? undefined,
        submodelId: entry.submodelId,
        categoryId: entry.categoryId,
        categoryLabel: entry.categoryLabel,
      },
      children: sectionChildren,
    };

    categoryNode.children.push(submodelNode);
  }

  const nodes = Array.from(categoryMap.values()).map((category) => ({
    ...category,
    status: {
      completion: completionFromChildren(category.children),
    },
  }));

  return nodes;
}
