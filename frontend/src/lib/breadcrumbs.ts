import { useLocation, useParams } from 'react-router-dom';

export type BreadcrumbItem = {
  label: string;
  href?: string;
};

const SEGMENT_LABELS: Record<string, string> = {
  console: 'Dashboard',
  dpps: 'DPPs',
  masters: 'Masters',
  templates: 'Templates',
  carriers: 'Data Carriers',
  connectors: 'Connectors',
  compliance: 'Compliance',
  epcis: 'Supply Chain',
  'batch-import': 'Batch Import',
  audit: 'Audit Trail',
  tenants: 'Tenants',
  settings: 'Settings',
  edit: 'Edit',
};

export function useBreadcrumbs(): BreadcrumbItem[] {
  const location = useLocation();
  const params = useParams();

  const segments = location.pathname.split('/').filter(Boolean);
  const items: BreadcrumbItem[] = [];

  // Always start with Dashboard for /console routes
  if (segments[0] !== 'console') return items;

  items.push({ label: 'Dashboard', href: '/console' });

  for (let i = 1; i < segments.length; i++) {
    const segment = segments[i];
    const path = '/' + segments.slice(0, i + 1).join('/');

    // Skip raw param values that we handle specially
    if (segment === params.dppId) {
      items.push({
        label: segment.slice(0, 8),
        href: path,
      });
      continue;
    }

    if (segment === params.templateKey) {
      // templateKey always follows "edit", so label it as "Edit {key}"
      const prev = items[items.length - 1];
      if (prev?.label === 'Edit') {
        prev.label = `Edit ${segment}`;
        prev.href = path;
      } else {
        items.push({ label: segment });
      }
      continue;
    }

    const label = SEGMENT_LABELS[segment] || segment;
    items.push({ label, href: path });
  }

  // Last item should not be a link (current page)
  if (items.length > 0) {
    delete items[items.length - 1].href;
  }

  return items;
}
