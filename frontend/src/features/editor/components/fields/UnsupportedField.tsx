import { AlertTriangle } from 'lucide-react';
import type { DefinitionNode } from '../../types/definition';
import { getNodeLabel, getNodeDescription } from '../../utils/pathUtils';

type UnsupportedFieldProps = {
  name: string;
  node: DefinitionNode;
  reason: string;
};

export function UnsupportedField({ name, node, reason }: UnsupportedFieldProps) {
  const label = getNodeLabel(node, name.split('.').pop() ?? name);
  const description = getNodeDescription(node);
  const semanticId = node.semanticId ?? 'n/a';

  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-4" data-field-path={name}>
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-900">
        <AlertTriangle className="h-4 w-4" />
        <span>{label}</span>
      </div>
      {description && <p className="text-xs text-amber-900/80">{description}</p>}
      <p className="mt-2 text-xs text-amber-900/80">
        Unsupported field. {reason}
      </p>
      <p className="mt-1 font-mono text-[11px] text-amber-900/80">
        modelType={node.modelType} semanticId={semanticId}
      </p>
    </div>
  );
}
