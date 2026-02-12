import type { DppOutlineNode } from '../types';

function matchesNode(node: DppOutlineNode, query: string): boolean {
  if (!query) return true;
  const haystack = [
    node.label,
    node.path,
    node.idShort,
    node.semanticId,
    node.searchableText,
    typeof node.meta?.templateKey === 'string' ? node.meta.templateKey : '',
    typeof node.meta?.categoryLabel === 'string' ? node.meta.categoryLabel : '',
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  return haystack.includes(query);
}

function filterNode(node: DppOutlineNode, query: string): DppOutlineNode | null {
  const filteredChildren = node.children
    .map((child) => filterNode(child, query))
    .filter((child): child is DppOutlineNode => Boolean(child));

  if (matchesNode(node, query) || filteredChildren.length > 0) {
    return {
      ...node,
      children: filteredChildren,
    };
  }

  return null;
}

export function filterOutlineNodes(
  nodes: DppOutlineNode[],
  query: string,
): DppOutlineNode[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return nodes;

  return nodes
    .map((node) => filterNode(node, normalized))
    .filter((node): node is DppOutlineNode => Boolean(node));
}
