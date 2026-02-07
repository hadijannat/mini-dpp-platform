import { Controller, type Control } from 'react-hook-form';
import type { DefinitionNode } from '../../types/definition';
import type { UISchema } from '../../types/uiSchema';
import { FieldWrapper } from '../FieldWrapper';
import { CollapsibleSection } from '../CollapsibleSection';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';

type EntityFieldProps = {
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

export function EntityField({ name, control, node, schema, depth, renderNode }: EntityFieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const defaultEntityType = node.entityType ?? 'SelfManagedEntity';
  const statements = node.statements ?? [];
  const statementsSchema = schema?.properties?.statements;

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const current =
          field.value && typeof field.value === 'object' && !Array.isArray(field.value)
            ? (field.value as Record<string, unknown>)
            : { entityType: defaultEntityType, globalAssetId: '', statements: {} };

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
          >
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500">Entity Type</label>
                <select
                  className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
                  value={(current.entityType as string) ?? defaultEntityType}
                  onChange={(e) => {
                    field.onChange({ ...current, entityType: e.target.value });
                  }}
                >
                  <option value="SelfManagedEntity">SelfManagedEntity</option>
                  <option value="CoManagedEntity">CoManagedEntity</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500">Global Asset ID</label>
                <input
                  type="text"
                  className="mt-1 w-full border rounded-md px-3 py-2 text-sm"
                  value={(current.globalAssetId as string) ?? ''}
                  onChange={(e) => {
                    field.onChange({ ...current, globalAssetId: e.target.value });
                  }}
                />
              </div>
              {statements.length > 0 ? (
                <CollapsibleSection
                  title="Statements"
                  depth={depth + 1}
                  childCount={statements.length}
                >
                  {statements.map((stmt, index) => {
                    const stmtId = stmt.idShort ?? `Statement${index + 1}`;
                    const stmtPath = `${name}.statements.${stmtId}`;
                    const stmtSchema = statementsSchema?.properties?.[stmtId];
                    return (
                      <div key={stmtPath}>
                        {renderNode({
                          node: stmt,
                          basePath: stmtPath,
                          depth: depth + 2,
                          schema: stmtSchema,
                          control,
                        })}
                      </div>
                    );
                  })}
                </CollapsibleSection>
              ) : (
                Boolean(current.statements &&
                  typeof current.statements === 'object' &&
                  Object.keys(current.statements as Record<string, unknown>).length > 0) && (
                    <div className="border rounded-md p-3 bg-muted/50">
                      <p className="text-xs text-muted-foreground mb-2">Statements</p>
                      <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                        {JSON.stringify(current.statements, null, 2)}
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
