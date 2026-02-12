import type { LangStringSet, DefinitionNode } from '../types/definition';
import type { UISchema } from '../types/uiSchema';

export function pathToKey(path: Array<string | number>): string {
  return path.map(String).join('.');
}

export function getValueAtPath(data: unknown, path: Array<string | number>): unknown {
  let current: unknown = data;
  for (const segment of path) {
    if (current == null) return undefined;
    current = (current as Record<string | number, unknown>)[segment];
  }
  return current;
}

export function setValueAtPath<T>(data: T, path: Array<string | number>, value: unknown): T {
  if (path.length === 0) return data;
  const [head, ...tail] = path;
  const key = typeof head === 'number' ? head : String(head);
  const clone: Record<string | number, unknown> = Array.isArray(data)
    ? [...(data as unknown[])] as unknown as Record<string | number, unknown>
    : { ...(data as Record<string, unknown>) };
  if (tail.length === 0) {
    clone[key] = value;
    return clone as T;
  }
  const existing = clone[key];
  const nextContainer =
    existing && typeof existing === 'object'
      ? existing
      : typeof tail[0] === 'number'
        ? []
        : {};
  clone[key] = setValueAtPath(nextContainer, tail, value);
  return clone as T;
}

export function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
  return false;
}

export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((item, idx) => deepEqual(item, b[idx]));
  }
  if (typeof a === 'object' && typeof b === 'object') {
    const aObj = a as Record<string, unknown>;
    const bObj = b as Record<string, unknown>;
    const aKeys = Object.keys(aObj);
    const bKeys = Object.keys(bObj);
    if (aKeys.length !== bKeys.length) return false;
    return aKeys.every((key) => deepEqual(aObj[key], bObj[key]));
  }
  return false;
}

export function pickLangValue(value?: LangStringSet): string | undefined {
  if (!value) return undefined;
  if (value.en) return value.en;
  const first = Object.values(value)[0];
  return first ?? undefined;
}

export function getNodeLabel(node: DefinitionNode, fallback: string): string {
  return (
    node.smt?.form_title ??
    pickLangValue(node.displayName) ??
    node.idShort ??
    fallback
  );
}

export function getNodeDescription(node: DefinitionNode): string | undefined {
  return node.smt?.form_info ?? pickLangValue(node.description);
}

export function isNodeRequired(node: DefinitionNode): boolean {
  return node.smt?.cardinality === 'One' || node.smt?.cardinality === 'OneToMany';
}

export function extractSemanticId(submodel: Record<string, unknown>): string | null {
  const values = extractSemanticIds(submodel);
  return values.length > 0 ? values[0] : null;
}

export function extractSemanticIds(submodel: Record<string, unknown>): string[] {
  const semanticId = submodel?.semanticId as { keys?: Array<{ value?: unknown }> } | undefined;
  if (!semanticId || !Array.isArray(semanticId.keys)) {
    return [];
  }
  const values: string[] = [];
  for (const key of semanticId.keys) {
    if (!key?.value) continue;
    const value = String(key.value).trim();
    if (!value) continue;
    values.push(value);
  }
  return values;
}

export function getSchemaAtPath(
  schema: UISchema | undefined,
  path: Array<string | number>,
): UISchema | undefined {
  let current: UISchema | undefined = schema;
  for (const segment of path) {
    if (!current) return undefined;
    if (typeof segment === 'number') {
      current = current.items;
      continue;
    }
    if (current.type === 'object' && current.properties) {
      current = current.properties[segment];
      continue;
    }
    if (current.type === 'array') {
      current = current.items;
      continue;
    }
    return current;
  }
  return current;
}

export function definitionPathToSegments(
  path: string,
  rootIdShort?: string,
): Array<string | '[]'> {
  const parts = path.split('/').filter(Boolean);
  const trimmed = rootIdShort && parts[0] === rootIdShort ? parts.slice(1) : parts;
  const segments: Array<string | '[]'> = [];
  for (const part of trimmed) {
    if (part.endsWith('[]')) {
      segments.push(part.slice(0, -2));
      segments.push('[]');
    } else {
      segments.push(part);
    }
  }
  return segments;
}

export function getValuesAtPattern(data: unknown, segments: Array<string | '[]'>): unknown[] {
  let current: unknown[] = [data];
  for (const segment of segments) {
    const next: unknown[] = [];
    if (segment === '[]') {
      for (const value of current) {
        if (Array.isArray(value)) {
          next.push(...value);
        }
      }
    } else {
      for (const value of current) {
        if (Array.isArray(value)) {
          value.forEach((entry: unknown) => {
            if (entry && typeof entry === 'object') {
              next.push((entry as Record<string, unknown>)[segment]);
            }
          });
        } else if (value && typeof value === 'object') {
          next.push((value as Record<string, unknown>)[segment]);
        }
      }
    }
    current = next;
    if (current.length === 0) break;
  }
  return current;
}
