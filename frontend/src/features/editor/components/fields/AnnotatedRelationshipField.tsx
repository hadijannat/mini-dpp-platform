import { Controller, type Control } from 'react-hook-form';
import type { DefinitionNode } from '../../types/definition';
import type { UISchema } from '../../types/uiSchema';
import { FieldWrapper } from '../FieldWrapper';
import { CollapsibleSection } from '../CollapsibleSection';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

type AnnotatedRelationshipFieldProps = {
  name: string;
  control: Control<Record<string, unknown>>;
  node: DefinitionNode;
  schema?: UISchema;
  depth: number;
  readOnly?: boolean;
  renderNode: (props: {
    node: DefinitionNode;
    basePath: string;
    depth: number;
    schema?: UISchema;
    control: Control<Record<string, unknown>>;
  }) => React.ReactNode;
};

export function AnnotatedRelationshipField({
  name,
  control,
  node,
  schema,
  depth,
  renderNode,
}: AnnotatedRelationshipFieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const annotations = node.annotations ?? [];
  const annotationsSchema = schema?.properties?.annotations;

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const current =
          field.value && typeof field.value === 'object' && !Array.isArray(field.value)
            ? (field.value as Record<string, unknown>)
            : { first: null, second: null, annotations: {} };

        const renderRef = (refKey: 'first' | 'second', refLabel: string) => {
          const ref = current[refKey] as Record<string, unknown> | null;
          return (
            <div className="border rounded-md p-3">
              <p className="text-xs font-medium text-muted-foreground mb-2">{refLabel}</p>
              {ref ? (
                <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                  {JSON.stringify(ref, null, 2)}
                </pre>
              ) : (
                <input
                  type="text"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  placeholder={`${refLabel} reference (JSON)`}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      field.onChange({ ...current, [refKey]: parsed });
                    } catch {
                      // Wait for valid JSON
                    }
                  }}
                />
              )}
            </div>
          );
        };

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
          >
            <div className="space-y-3">
              {renderRef('first', 'First Reference')}
              {renderRef('second', 'Second Reference')}
              {annotations.length > 0 ? (
                <CollapsibleSection
                  title="Annotations"
                  depth={depth + 1}
                  childCount={annotations.length}
                >
                  {annotations.map((ann, index) => {
                    const annId = ann.idShort ?? `Annotation${index + 1}`;
                    const annPath = `${name}.annotations.${annId}`;
                    const annSchema = annotationsSchema?.properties?.[annId];
                    return (
                      <div key={annPath}>
                        {renderNode({
                          node: ann,
                          basePath: annPath,
                          depth: depth + 2,
                          schema: annSchema,
                          control,
                        })}
                      </div>
                    );
                  })}
                </CollapsibleSection>
              ) : (
                Boolean(current.annotations &&
                  typeof current.annotations === 'object' &&
                  Object.keys(current.annotations as Record<string, unknown>).length > 0) && (
                    <div className="border rounded-md p-3 bg-muted/50">
                      <p className="text-xs text-muted-foreground mb-2">Annotations</p>
                      <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                        {JSON.stringify(current.annotations, null, 2)}
                      </pre>
                    </div>
                  )
              )}
            </div>
          </FieldWrapper>
        );
      }}
    />
  );
}
