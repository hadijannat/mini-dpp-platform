import { useRef } from 'react';
import { Controller, type Control } from 'react-hook-form';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { DefinitionNode } from '../../types/definition';
import type { EditorContext } from '../../types/formTypes';
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
    editorContext?: EditorContext;
  }) => React.ReactNode;
  editorContext?: EditorContext;
};

export function ListField({
  name,
  control,
  node,
  schema,
  depth,
  renderNode,
  editorContext,
}: ListFieldProps) {
  const label = getNodeLabel(node, node.idShort ?? name);
  const description = getNodeDescription(node);
  const required = isNodeRequired(node);
  const formUrl = node.smt?.form_url ?? undefined;
  const itemsSchema = schema?.items;
  const itemDefinition = node.items ?? undefined;
  const orderRelevant = node.orderRelevant ?? false;
  const allowedIdShort = schema?.['x-allowed-id-short'] ?? [];
  const editIdShort = schema?.['x-edit-id-short'] ?? false;
  const namingRule = schema?.['x-naming'];
  const listUnsupported =
    !itemDefinition ||
    Boolean(schema?.['x-unresolved-definition']) ||
    Boolean(itemsSchema?.['x-unresolved-definition']);
  const unsupportedReason =
    schema?.['x-unresolved-reason'] ??
    itemsSchema?.['x-unresolved-reason'] ??
    'missing list item definition';
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
            fieldPath={name}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400">
                {list.length} item{list.length !== 1 ? 's' : ''}
              </span>
              <button
                type="button"
                className="text-sm text-primary hover:text-primary/80 disabled:cursor-not-allowed disabled:text-muted-foreground"
                aria-label={`Add item to ${label}`}
                disabled={
                  listUnsupported || (allowedIdShort.length > 0 && list.length >= allowedIdShort.length)
                }
                onClick={() => {
                  const nextItem = defaultValueForSchema(itemsSchema);
                  const suggestedIdShort = allowedIdShort[list.length];
                  const withIdShort =
                    !editIdShort &&
                    suggestedIdShort &&
                    nextItem &&
                    typeof nextItem === 'object' &&
                    !Array.isArray(nextItem)
                      ? { ...(nextItem as Record<string, unknown>), idShort: suggestedIdShort }
                      : nextItem;
                  const next = [...list, withIdShort];
                  field.onChange(next);
                }}
              >
                Add item
              </button>
            </div>
            {listUnsupported && (
              <p className="mb-2 text-xs text-amber-700">
                Unsupported list rendering: {unsupportedReason}.
              </p>
            )}
            {(allowedIdShort.length > 0 || namingRule) && (
              <p className="mb-2 text-xs text-muted-foreground">
                {allowedIdShort.length > 0 && (
                  <>Allowed idShorts: {allowedIdShort.join(', ')}. </>
                )}
                {namingRule && <>Naming rule: {namingRule}.</>}
              </p>
            )}
            {schema?.['x-unresolved-definition'] && (
              <p className="mb-2 text-xs text-amber-700">
                Definition unresolved: {schema['x-unresolved-reason'] ?? 'missing list item definition'}.
              </p>
            )}
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
                editorContext={editorContext}
                onRemove={(index) => {
                  const next = list.filter((_, idx) => idx !== index);
                  field.onChange(next);
                }}
                onMove={(from, to) => {
                  if (to < 0 || to >= list.length || from === to) return;
                  const next = [...list];
                  const [moved] = next.splice(from, 1);
                  next.splice(to, 0, moved);
                  field.onChange(next);
                }}
                orderRelevant={orderRelevant}
                listUnsupported={listUnsupported}
                unsupportedReason={unsupportedReason}
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
                    editorContext={editorContext}
                    onRemove={() => {
                      const next = list.filter((_, idx) => idx !== index);
                      field.onChange(next);
                    }}
                    onMove={(to) => {
                      if (to < 0 || to >= list.length || to === index) return;
                      const next = [...list];
                      const [moved] = next.splice(index, 1);
                      next.splice(to, 0, moved);
                      field.onChange(next);
                    }}
                    listLength={list.length}
                    orderRelevant={orderRelevant}
                    listUnsupported={listUnsupported}
                    unsupportedReason={unsupportedReason}
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
  editorContext,
  onRemove,
  onMove,
  orderRelevant,
  listLength,
  listUnsupported,
  unsupportedReason,
}: {
  name: string;
  index: number;
  control: Control<Record<string, unknown>>;
  depth: number;
  itemDefinition?: DefinitionNode;
  itemsSchema?: UISchema;
  renderNode: ListFieldProps['renderNode'];
  editorContext?: EditorContext;
  onRemove: () => void;
  onMove: (toIndex: number) => void;
  orderRelevant: boolean;
  listLength: number;
  listUnsupported: boolean;
  unsupportedReason: string;
}) {
  const itemPath = `${name}.${index}`;
  return (
    <div className="border rounded-md p-3">
      <div className="flex justify-end">
        {orderRelevant && (
          <div className="mr-2 flex gap-1">
            <button
              type="button"
              className="text-xs text-gray-500 hover:text-gray-700 disabled:opacity-40"
              aria-label={`Move item ${index + 1} up`}
              onClick={() => onMove(index - 1)}
              disabled={index === 0}
            >
              Up
            </button>
            <button
              type="button"
              className="text-xs text-gray-500 hover:text-gray-700 disabled:opacity-40"
              aria-label={`Move item ${index + 1} down`}
              onClick={() => onMove(index + 1)}
              disabled={index >= listLength - 1}
            >
              Down
            </button>
          </div>
        )}
        <button
          type="button"
          className="text-xs text-red-500 hover:text-red-600"
          aria-label={`Remove item ${index + 1}`}
          onClick={onRemove}
        >
          Remove
        </button>
      </div>
      <div className="mt-2">
        {listUnsupported ? (
          <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
            Unsupported list item renderer: {unsupportedReason}.
          </p>
        ) : itemDefinition
          ? renderNode({
              node: itemDefinition,
              basePath: itemPath,
              depth: depth + 1,
              schema: itemsSchema,
              control,
              editorContext,
            })
          : null}
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
  editorContext,
  onRemove,
  onMove,
  orderRelevant,
  listUnsupported,
  unsupportedReason,
}: {
  list: unknown[];
  name: string;
  control: Control<Record<string, unknown>>;
  depth: number;
  itemDefinition?: DefinitionNode;
  itemsSchema?: UISchema;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  renderNode: ListFieldProps['renderNode'];
  editorContext?: EditorContext;
  onRemove: (index: number) => void;
  onMove: (fromIndex: number, toIndex: number) => void;
  orderRelevant: boolean;
  listUnsupported: boolean;
  unsupportedReason: string;
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
              editorContext={editorContext}
              onRemove={() => onRemove(virtualItem.index)}
              onMove={(to) => onMove(virtualItem.index, to)}
              listLength={list.length}
              orderRelevant={orderRelevant}
              listUnsupported={listUnsupported}
              unsupportedReason={unsupportedReason}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
