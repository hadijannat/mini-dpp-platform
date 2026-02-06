import type { AASRendererProps } from '../types/formTypes';
import type { UISchema } from '../types/uiSchema';
import type { DefinitionNode } from '../types/definition';
import type { Control } from 'react-hook-form';
import { getSchemaAtPath } from '../utils/pathUtils';
import { PropertyField } from './fields/PropertyField';
import { MultiLangField } from './fields/MultiLangField';
import { RangeField } from './fields/RangeField';
import { FileField } from './fields/FileField';
import { ReferenceField } from './fields/ReferenceField';
import { EntityField } from './fields/EntityField';
import { RelationshipField } from './fields/RelationshipField';
import { AnnotatedRelationshipField } from './fields/AnnotatedRelationshipField';
import { ReadOnlyField } from './fields/ReadOnlyField';
import { CollectionField } from './fields/CollectionField';
import { ListField } from './fields/ListField';

/** Recursive render callback passed to container fields to break import cycles */
function renderNode(props: {
  node: DefinitionNode;
  basePath: string;
  depth: number;
  schema?: UISchema;
  control: Control<Record<string, unknown>>;
}): React.ReactNode {
  return <AASRenderer {...props} />;
}

/**
 * Recursive type-dispatch renderer for AAS SubmodelElements.
 * Replaces the monolithic renderDefinitionNode / renderField functions.
 */
export function AASRenderer({ node, basePath, depth, schema, control }: AASRendererProps) {
  const accessMode = node.smt?.access_mode?.toLowerCase();
  const readOnly = accessMode === 'readonly' || accessMode === 'read-only';

  const fieldProps = {
    name: basePath,
    control,
    node,
    schema,
    depth,
    readOnly,
  };

  // Read-only access mode or read-only element types
  if (readOnly) {
    return <ReadOnlyField {...fieldProps} />;
  }

  switch (node.modelType) {
    case 'SubmodelElementCollection':
      return (
        <CollectionField
          name={basePath}
          control={control}
          node={node}
          schema={schema}
          depth={depth}
          renderNode={renderNode}
        />
      );

    case 'SubmodelElementList':
      return (
        <ListField
          name={basePath}
          control={control}
          node={node}
          schema={schema}
          depth={depth}
          renderNode={renderNode}
        />
      );

    case 'MultiLanguageProperty':
      return <MultiLangField {...fieldProps} />;

    case 'Range':
      return <RangeField {...fieldProps} />;

    case 'File':
      return <FileField {...fieldProps} />;

    case 'ReferenceElement':
      return <ReferenceField {...fieldProps} />;

    case 'Entity':
      return <EntityField {...fieldProps} />;

    case 'RelationshipElement':
      return <RelationshipField {...fieldProps} />;

    case 'AnnotatedRelationshipElement':
      return <AnnotatedRelationshipField {...fieldProps} />;

    case 'Blob':
    case 'Operation':
    case 'Capability':
    case 'BasicEventElement':
      return <ReadOnlyField {...fieldProps} />;

    case 'Property':
    default:
      return <PropertyField {...fieldProps} />;
  }
}

/**
 * Renders a list of top-level definition nodes.
 * Resolves schema from UISchema by path for each node.
 */
export function AASRendererList({
  nodes,
  basePath,
  depth,
  rootSchema,
  control,
}: {
  nodes: DefinitionNode[];
  basePath: string;
  depth: number;
  rootSchema?: UISchema;
  control: Control<Record<string, unknown>>;
}) {
  return (
    <div className="space-y-4">
      {nodes.map((node, index) => {
        const nodeId = node.idShort ?? `Item${index + 1}`;
        const fieldPath = basePath ? `${basePath}.${nodeId}` : nodeId;
        const pathSegments = fieldPath.split('.');
        const schemaNode = getSchemaAtPath(rootSchema, pathSegments);
        return (
          <AASRenderer
            key={fieldPath}
            node={node}
            basePath={fieldPath}
            depth={depth}
            schema={schemaNode}
            control={control}
          />
        );
      })}
    </div>
  );
}
