export type DppOutlineKind =
  | 'root'
  | 'category'
  | 'submodel'
  | 'section'
  | 'field';

export type DppOutlineCompletion = 'empty' | 'partial' | 'complete';

export type DppOutlineRisk = 'low' | 'medium' | 'high' | 'critical';

export type DppOutlineTarget =
  | {
      type: 'route';
      href: string;
      query?: Record<string, string | undefined>;
    }
  | {
      type: 'dom';
      path: string;
    };

export type DppOutlineStatus = {
  required?: boolean;
  completion?: DppOutlineCompletion;
  requiredTotal?: number;
  requiredCompleted?: number;
  errors?: number;
  warnings?: number;
  risk?: DppOutlineRisk;
};

export type DppOutlineMeta = {
  templateKey?: string;
  submodelId?: string;
  categoryId?: string;
  categoryLabel?: string;
  outlineKey?: string;
  [key: string]: string | number | boolean | undefined;
};

export type DppOutlineNode = {
  id: string;
  kind: DppOutlineKind;
  label: string;
  path: string;
  idShort?: string;
  semanticId?: string;
  searchableText?: string;
  status?: DppOutlineStatus;
  target?: DppOutlineTarget;
  meta?: DppOutlineMeta;
  children: DppOutlineNode[];
};

export function createOutlineNodeId(kind: DppOutlineKind, path: string): string {
  return `${kind}:${path}`;
}

export function completionFromChildren(
  children: DppOutlineNode[],
): DppOutlineCompletion {
  if (children.length === 0) return 'empty';
  const states = children
    .map((child) => child.status?.completion)
    .filter((value): value is DppOutlineCompletion => Boolean(value));

  if (states.length === 0) return 'empty';
  if (states.every((state) => state === 'complete')) return 'complete';
  if (states.every((state) => state === 'empty')) return 'empty';
  return 'partial';
}
