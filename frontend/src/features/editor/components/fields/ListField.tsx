import { useRef } from 'react';
import { Controller, type Control } from 'react-hook-form';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { DefinitionNode } from '../../types/definition';
import type { UISchema } from '../../types/uiSchema';
import { FieldWrapper } from '../FieldWrapper';
import { getNodeLabel, getNodeDescription, isNodeRequired } from '../../utils/pathUtils';
import { defaultValueForSchema } from '../../utils/formDefaults';

const VIRTUALIZE_THRESHOLD = 20;
const ESTIMATED_ITEM_HEIGHT = 120;

type ListFieldProps = {
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

export function ListField({
  name,
  control,
  node,
  schema,
  depth,
  renderNode,
}: ListFieldProps) {
  const label = getNodeLabel(node, node.idShort ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const itemsSchema = schema?.items;
  const itemDefinition = node.items ?? undefined;
  const scrollRef = useRef<HTMLDivElement>(null);

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const list = Array.isArray(field.value) ? (field.value as unknown[]) : [];
        const useVirtual = list.length > VIRTUALIZE_THRESHOLD;

        return (
          <FieldWrapper
            label={label}
            required={required}
            description={description}
            formUrl={formUrl}
            error={fieldState.error?.message}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400">
                {list.length} item{list.length !== 1 ? 's' : ''}
              </span>
              <button
                type="button"
                className="text-sm text-primary-600 hover:text-primary-700"
                onClick={() => {
                  const next = [...list, defaultValueForSchema(itemsSchema)];
                  field.onChange(next);
                }}
              >
                Add item
              </button>
            </div>
            {list.length === 0 && (
              <p className="text-xs text-gray-400">No items yet.</p>
            )}
            {useVirtual ? (
              <VirtualizedList
                list={list}
                name={name}
                control={control}
                depth={depth}
                itemDefinition={itemDefinition}
                itemsSchema={itemsSchema}
                scrollRef={scrollRef}
                renderNode={renderNode}
                onRemove={(index) => {
                  const next = list.filter((_, idx) => idx !== index);
                  field.onChange(next);
                }}
              />
            ) : (
              <div className="space-y-3">
                {list.map((_, index) => (
                  <ListItem
                    key={`${name}.${index}`}
                    name={name}
                    index={index}
                    control={control}
                    depth={depth}
                    itemDefinition={itemDefinition}
                    itemsSchema={itemsSchema}
                    renderNode={renderNode}
                    onRemove={() => {
                      const next = list.filter((_, idx) => idx !== index);
                      field.onChange(next);
                    }}
                  />
                ))}
              </div>
            )}
          </FieldWrapper>
        );
      }}
    />
  );
}

function ListItem({
  name,
  index,
  control,
  depth,
  itemDefinition,
  itemsSchema,
  renderNode,
  onRemove,
}: {
  name: string;
  index: number;
  control: Control<Record<string, unknown>>;
  depth: number;
  itemDefinition?: DefinitionNode;
  itemsSchema?: UISchema;
  renderNode: ListFieldProps['renderNode'];
  onRemove: () => void;
}) {
  const itemPath = `${name}.${index}`;
  return (
    <div className="border rounded-md p-3">
      <div className="flex justify-end">
        <button
          type="button"
          className="text-xs text-red-500 hover:text-red-600"
          onClick={onRemove}
        >
          Remove
        </button>
      </div>
      <div className="mt-2">
        {itemDefinition
          ? renderNode({
              node: itemDefinition,
              basePath: itemPath,
              depth: depth + 1,
              schema: itemsSchema,
              control,
            })
          : renderNode({
              node: { modelType: 'Property', idShort: `Item ${index + 1}` },
              basePath: itemPath,
              depth: depth + 1,
              schema: itemsSchema ?? { type: 'string' },
              control,
            })}
      </div>
    </div>
  );
}

function VirtualizedList({
  list,
  name,
  control,
  depth,
  itemDefinition,
  itemsSchema,
  scrollRef,
  renderNode,
  onRemove,
}: {
  list: unknown[];
  name: string;
  control: Control<Record<string, unknown>>;
  depth: number;
  itemDefinition?: DefinitionNode;
  itemsSchema?: UISchema;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  renderNode: ListFieldProps['renderNode'];
  onRemove: (index: number) => void;
}) {
  const virtualizer = useVirtualizer({
    count: list.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ESTIMATED_ITEM_HEIGHT,
    overscan: 5,
  });

  return (
    <div ref={scrollRef as React.RefObject<HTMLDivElement>} className="max-h-96 overflow-auto">
      <div
        className="relative w-full"
        style={{ height: `${virtualizer.getTotalSize()}px` }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            className="absolute left-0 w-full"
            style={{
              top: `${virtualItem.start}px`,
              height: `${virtualItem.size}px`,
            }}
          >
            <ListItem
              name={name}
              index={virtualItem.index}
              control={control}
              depth={depth}
              itemDefinition={itemDefinition}
              itemsSchema={itemsSchema}
              renderNode={renderNode}
              onRemove={() => onRemove(virtualItem.index)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
