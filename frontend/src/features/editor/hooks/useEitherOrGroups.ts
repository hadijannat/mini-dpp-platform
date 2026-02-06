import { useMemo } from 'react';
import type { DefinitionNode, TemplateDefinition, FormData } from '../types/definition';
import { definitionPathToSegments, getValuesAtPattern, isEmptyValue } from '../utils/pathUtils';

type EitherOrGroup = {
  groupId: string;
  nodes: DefinitionNode[];
};

/**
 * Extracts EitherOr groups from the definition for cross-field validation.
 * Returns a validate function that checks if at least one member of each group has a value.
 */
export function useEitherOrGroups(definition?: TemplateDefinition) {
  const groups = useMemo(() => {
    if (!definition?.submodel?.elements?.length) return [];
    const groupMap: Record<string, DefinitionNode[]> = {};

    const visit = (node: DefinitionNode) => {
      const groupId = node.smt?.either_or;
      if (groupId) {
        groupMap[groupId] = groupMap[groupId] || [];
        groupMap[groupId].push(node);
      }
      node.children?.forEach(visit);
      if (node.items) visit(node.items);
    };

    definition.submodel.elements.forEach(visit);

    return Object.entries(groupMap).map(
      ([groupId, nodes]): EitherOrGroup => ({ groupId, nodes }),
    );
  }, [definition]);

  const validate = (data: FormData): string[] => {
    if (groups.length === 0) return [];
    const rootIdShort = definition?.submodel?.idShort;
    const errors: string[] = [];

    for (const { groupId, nodes } of groups) {
      const hasValue = nodes.some((node) => {
        if (!node.path) return false;
        const segments = definitionPathToSegments(node.path, rootIdShort);
        const values = getValuesAtPattern(data, segments);
        return values.some((value) => !isEmptyValue(value));
      });
      if (!hasValue) {
        errors.push(`Either-or group "${groupId}" requires at least one value.`);
      }
    }

    return errors;
  };

  return { groups, validate };
}
