import { useMemo } from 'react';
import type { DefinitionNode } from '../types/definition';

type ConceptDescription = {
  unit?: string;
  preferredName?: string;
};

/**
 * Extracts a map of semanticId -> unit/preferredName from the definition tree.
 * Used by FieldWrapper to display units alongside field labels.
 */
export function useConceptDescriptions(
  elements?: DefinitionNode[],
): Map<string, ConceptDescription> {
  return useMemo(() => {
    const map = new Map<string, ConceptDescription>();
    if (!elements) return map;

    const visit = (node: DefinitionNode) => {
      if (node.semanticId) {
        map.set(node.semanticId, {
          preferredName: node.displayName?.en,
        });
      }
      node.children?.forEach(visit);
      if (node.items) visit(node.items);
    };

    elements.forEach(visit);
    return map;
  }, [elements]);
}
