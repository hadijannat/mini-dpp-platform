import type { DefinitionNode, TemplateDefinition } from '@/features/editor/types/definition';
import { isNodeRequired } from '@/features/editor/utils/pathUtils';
import { completionFromChildren, createOutlineNodeId, type DppOutlineNode } from '../types';

export type EditorFieldError = {
  path: string;
  message: string;
};

type BuildSubmodelEditorOutlineParams = {
  templateDefinition?: TemplateDefinition;
  formData: Record<string, unknown>;
  fieldErrors: EditorFieldError[];
};

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
  return false;
}

function getPathValue(data: unknown, path: string): unknown {
  if (!path) return data;
  const segments = path.split('.').filter(Boolean);
  let current: unknown = data;

  for (const segment of segments) {
    if (current == null) return undefined;
    if (Array.isArray(current)) {
      const index = Number(segment);
      if (!Number.isInteger(index)) return undefined;
      current = current[index];
      continue;
    }
    if (typeof current === 'object') {
      current = (current as Record<string, unknown>)[segment];
      continue;
    }
    return undefined;
  }

  return current;
}

function countPathErrors(path: string, fieldErrors: EditorFieldError[]): number {
  return fieldErrors.filter((entry) => entry.path === path || entry.path.startsWith(`${path}.`)).length;
}

function definitionChildren(node: DefinitionNode): DefinitionNode[] {
  const children = Array.isArray(node.children) ? node.children : [];
  const statements = Array.isArray(node.statements) ? node.statements : [];
  const annotations = Array.isArray(node.annotations) ? node.annotations : [];
  return [...children, ...statements, ...annotations];
}

function buildListItemNode(params: {
  node: DefinitionNode;
  itemPath: string;
  itemIndex: number;
  itemValue: unknown;
  fieldErrors: EditorFieldError[];
}): DppOutlineNode {
  const { node, itemPath, itemIndex, itemValue, fieldErrors } = params;
  const children = definitionChildren(node);

  const itemChildren =
    children.length > 0
      ? children
          .map((child) => {
            if (!child.idShort) return null;
            return buildDefinitionNode({
              node: child,
              path: `${itemPath}.${child.idShort}`,
              value: getPathValue(itemValue, child.idShort),
              fieldErrors,
            });
          })
          .filter((child): child is DppOutlineNode => Boolean(child))
      : [];

  const completion =
    itemChildren.length > 0
      ? completionFromChildren(itemChildren)
      : isEmptyValue(itemValue)
        ? 'empty'
        : 'complete';

  return {
    id: createOutlineNodeId('section', itemPath),
    kind: 'section',
    label: `Item ${itemIndex + 1}`,
    path: itemPath,
    searchableText: `${node.idShort ?? ''} item ${itemIndex + 1}`,
    status: {
      completion,
      errors: countPathErrors(itemPath, fieldErrors),
    },
    target: {
      type: 'dom',
      path: itemPath,
    },
    children: itemChildren,
  };
}

function buildDefinitionNode(params: {
  node: DefinitionNode;
  path: string;
  value: unknown;
  fieldErrors: EditorFieldError[];
}): DppOutlineNode {
  const { node, path, value, fieldErrors } = params;
  const children = definitionChildren(node);
  const required = isNodeRequired(node);

  if (node.modelType === 'SubmodelElementList' && node.items) {
    const list = Array.isArray(value) ? value : [];
    const listChildren = list.map((itemValue, index) =>
      buildListItemNode({
        node: node.items!,
        itemPath: `${path}.${index}`,
        itemIndex: index,
        itemValue,
        fieldErrors,
      }),
    );

    const completion =
      listChildren.length > 0
        ? completionFromChildren(listChildren)
        : required
          ? 'empty'
          : 'partial';

    return {
      id: createOutlineNodeId('section', path),
      kind: 'section',
      label: node.idShort ?? path,
      path,
      idShort: node.idShort,
      semanticId: node.semanticId ?? undefined,
      searchableText: `${node.idShort ?? ''} ${path}`,
      status: {
        required,
        completion,
        errors: countPathErrors(path, fieldErrors),
      },
      target: {
        type: 'dom',
        path,
      },
      children: listChildren,
    };
  }

  const renderedChildren = children
    .map((child) => {
      if (!child.idShort) return null;
      const childPath = `${path}.${child.idShort}`;
      return buildDefinitionNode({
        node: child,
        path: childPath,
        value: getPathValue(value, child.idShort),
        fieldErrors,
      });
    })
    .filter((child): child is DppOutlineNode => Boolean(child));

  const kind = renderedChildren.length > 0 ? 'section' : 'field';
  const completion =
    renderedChildren.length > 0
      ? completionFromChildren(renderedChildren)
      : isEmptyValue(value)
        ? 'empty'
        : 'complete';

  return {
    id: createOutlineNodeId(kind, path),
    kind,
    label: node.idShort ?? path,
    path,
    idShort: node.idShort,
    semanticId: node.semanticId ?? undefined,
    searchableText: `${node.idShort ?? ''} ${path}`,
    status: {
      required,
      completion,
      errors: countPathErrors(path, fieldErrors),
    },
    target: {
      type: 'dom',
      path,
    },
    children: renderedChildren,
  };
}

export function buildSubmodelEditorOutline({
  templateDefinition,
  formData,
  fieldErrors,
}: BuildSubmodelEditorOutlineParams): DppOutlineNode[] {
  const sections = templateDefinition?.submodel?.elements ?? [];

  return sections
    .map((section, index) => {
      const idShort = section.idShort ?? `Section${index + 1}`;
      return buildDefinitionNode({
        node: section,
        path: idShort,
        value: formData[idShort],
        fieldErrors,
      });
    })
    .map((node) => ({
      ...node,
      status: {
        ...node.status,
        completion: node.status?.completion ?? 'empty',
      },
    }));
}
