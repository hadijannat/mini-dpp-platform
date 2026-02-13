import type { DefinitionNode, TemplateDefinition } from '../types/definition';

export type PatchOperation = {
  op: 'set_value' | 'set_multilang' | 'add_list_item' | 'remove_list_item' | 'set_file_ref';
  path: string;
  value?: unknown;
  index?: number;
};

export function buildPatchOperations(
  definition: TemplateDefinition | undefined,
  currentData: Record<string, unknown>,
  nextData: Record<string, unknown>,
): PatchOperation[] {
  const operations: PatchOperation[] = [];
  const roots = definition?.submodel?.elements ?? [];
  for (const root of roots) {
    const idShort = root.idShort;
    if (!idShort || !(idShort in nextData)) continue;
    buildNodeOperations({
      node: root,
      currentValue: currentData[idShort],
      nextValue: nextData[idShort],
      path: idShort,
      operations,
    });
  }
  return operations;
}

function buildNodeOperations(args: {
  node: DefinitionNode;
  currentValue: unknown;
  nextValue: unknown;
  path: string;
  operations: PatchOperation[];
}) {
  const { node, currentValue, nextValue, path, operations } = args;
  if (node.modelType === 'SubmodelElementCollection') {
    if (!isRecord(nextValue)) return;
    for (const child of node.children ?? []) {
      const childId = child.idShort;
      if (!childId || !(childId in nextValue)) continue;
      const nextChildValue = nextValue[childId];
      const currentChildValue = isRecord(currentValue) ? currentValue[childId] : undefined;
      buildNodeOperations({
        node: child,
        currentValue: currentChildValue,
        nextValue: nextChildValue,
        path: `${path}/${childId}`,
        operations,
      });
    }
    return;
  }

  if (node.modelType === 'SubmodelElementList') {
    if (!Array.isArray(nextValue)) return;
    const currentList = Array.isArray(currentValue) ? currentValue : [];
    for (let index = currentList.length - 1; index >= nextValue.length; index -= 1) {
      operations.push({ op: 'remove_list_item', path, index });
    }

    if (node.items) {
      const shared = Math.min(currentList.length, nextValue.length);
      for (let index = 0; index < shared; index += 1) {
        buildNodeOperations({
          node: node.items,
          currentValue: currentList[index],
          nextValue: nextValue[index],
          path: `${path}/${index}`,
          operations,
        });
      }
    }

    for (let index = currentList.length; index < nextValue.length; index += 1) {
      const payload = nextValue[index];
      operations.push({
        op: 'add_list_item',
        path,
        value: isRecord(payload) ? payload : { value: payload },
      });
    }
    return;
  }

  if (node.modelType === 'MultiLanguageProperty') {
    if (!deepEqual(nextValue, currentValue) && isRecord(nextValue)) {
      operations.push({ op: 'set_multilang', path, value: nextValue });
    }
    return;
  }

  if (node.modelType === 'File' || node.modelType === 'Blob') {
    if (!deepEqual(nextValue, currentValue) && isRecord(nextValue)) {
      operations.push({
        op: 'set_file_ref',
        path,
        value: {
          contentType: nextValue.contentType,
          url: nextValue.value,
        },
      });
    }
    return;
  }

  if (!deepEqual(nextValue, currentValue)) {
    operations.push({ op: 'set_value', path, value: nextValue });
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function deepEqual(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  try {
    return JSON.stringify(left) === JSON.stringify(right);
  } catch {
    return false;
  }
}

