import type { Control } from 'react-hook-form';
import type { DefinitionNode } from '../../types/definition';
import type { UISchema } from '../../types/uiSchema';
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
  }) => React.ReactNode;
};

export function CollectionField({
  name,
  control,
  node,
  schema,
  depth,
  renderNode,
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
      childCount={children.length}
    >
      {children.map((child, index) => {
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
            })}
          </div>
        );
      })}
      {children.length === 0 && schema?.properties && (
        Object.entries(schema.properties).map(([key, childSchema]) => (
          <div key={name ? `${name}.${key}` : key}>
            {renderNode({
              node: { modelType: 'Property', idShort: key },
              basePath: name ? `${name}.${key}` : key,
              depth: depth + 1,
              schema: childSchema,
              control,
            })}
          </div>
        ))
      )}
    </CollapsibleSection>
  );
}
