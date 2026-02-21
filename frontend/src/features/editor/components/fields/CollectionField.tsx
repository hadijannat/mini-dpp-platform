import type { Control } from 'react-hook-form';
import type { DefinitionNode } from '../../types/definition';
import type { UISchema } from '../../types/uiSchema';
import type { EditorContext } from '../../types/formTypes';
import { CollapsibleSection } from '../CollapsibleSection';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

type CollectionFieldProps = {
  name: string;
  control: Control<Record<string, unknown>>;
  node: DefinitionNode;
  schema?: UISchema;
  depth: number;
  renderNode: (props: {
    node: DefinitionNode;
    basePath: string;
    depth: number;
    schema?: UISchema;
    control: Control<Record<string, unknown>>;
    editorContext?: EditorContext;
  }) => React.ReactNode;
  editorContext?: EditorContext;
};

export function CollectionField({
  name,
  control,
  node,
  schema,
  depth,
  renderNode,
  editorContext,
}: CollectionFieldProps) {
  const label = getNodeLabel(node, node.idShort ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const children = node.children ?? [];

  return (
    <CollapsibleSection
      title={label}
      required={required}
      description={description}
      depth={depth}
      fieldPath={name}
      childCount={children.length}
    >
      {schema?.['x-unresolved-definition'] && (
        <p className="mb-2 text-xs text-amber-700">
          Definition unresolved: {schema['x-unresolved-reason'] ?? 'missing structural definition'}.
        </p>
      )}
      {[...children]
        .sort((left, right) => {
          const leftOrder = typeof left.order === 'number' ? left.order : Number.MAX_SAFE_INTEGER;
          const rightOrder = typeof right.order === 'number' ? right.order : Number.MAX_SAFE_INTEGER;
          if (leftOrder !== rightOrder) return leftOrder - rightOrder;
          return String(left.idShort ?? '').localeCompare(String(right.idShort ?? ''));
        })
        .map((child, index) => {
        const childId = child.idShort ?? `Item${index + 1}`;
        const childPath = name ? `${name}.${childId}` : childId;
        const childSchema = schema?.properties?.[childId] ?? schema?.items;
        return (
          <div key={childPath}>
            {renderNode({
              node: child,
              basePath: childPath,
              depth: depth + 1,
              schema: childSchema,
              control,
              editorContext,
            })}
          </div>
        );
      })}
      {children.length === 0 && (
        <p className="text-xs text-amber-700">
          No renderable child nodes are available for this collection.
        </p>
      )}
    </CollapsibleSection>
  );
}
