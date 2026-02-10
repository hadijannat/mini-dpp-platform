import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { getApiErrorMessage, tenantApiFetch } from '@/lib/api';
import { useTenantSlug } from '@/lib/tenant';
import { PageHeader } from '@/components/page-header';
import { ActorBadge } from '@/components/actor-badge';
import { ErrorBanner } from '@/components/error-banner';
import { LoadingSpinner } from '@/components/loading-spinner';
import { Card } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface ActorSummary {
  subject: string;
  display_name?: string | null;
  email_masked?: string | null;
}

interface ActivityEvent {
  id: string;
  subject?: string | null;
  actor?: ActorSummary | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  decision?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

interface ActivityResponse {
  events: ActivityEvent[];
  count: number;
  total_count: number;
  limit: number;
  offset: number;
}

async function fetchActivityEvents(token?: string) {
  const response = await tenantApiFetch('/activity/events?limit=100&offset=0', {}, token);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch activity events'));
  }
  return response.json() as Promise<ActivityResponse>;
}

async function fetchResourceActivity(type: string, id: string, token?: string) {
  const response = await tenantApiFetch(
    `/activity/resources/${encodeURIComponent(type)}/${encodeURIComponent(id)}?limit=100&offset=0`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch resource activity'));
  }
  return response.json() as Promise<ActivityResponse>;
}

export default function ActivityPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [tenantSlug] = useTenantSlug();
  const [searchParams] = useSearchParams();

  const resourceType = searchParams.get('type');
  const resourceId = searchParams.get('id');
  const showingResource = Boolean(resourceType && resourceId);

  const queryKey = useMemo(
    () =>
      showingResource
        ? ['activity', tenantSlug, resourceType, resourceId]
        : ['activity', tenantSlug, 'events'],
    [showingResource, tenantSlug, resourceType, resourceId],
  );

  const { data, isLoading, isError, error } = useQuery({
    queryKey,
    queryFn: () => {
      if (showingResource && resourceType && resourceId) {
        return fetchResourceActivity(resourceType, resourceId, token);
      }
      return fetchActivityEvents(token);
    },
    enabled: Boolean(token),
  });

  const pageError = isError ? (error as Error) : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Activity"
        description={
          showingResource && resourceType && resourceId
            ? `Timeline for ${resourceType} ${resourceId.slice(0, 8)}...`
            : 'Tenant activity timeline'
        }
      />

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Failed to load activity'}
          showSignIn={false}
          onSignIn={() => {}}
        />
      )}

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Decision</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data?.events ?? []).map((event) => (
                <TableRow key={event.id}>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(event.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <ActorBadge actor={event.actor} fallbackSubject={event.subject || null} />
                  </TableCell>
                  <TableCell className="font-medium">{event.action}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {event.resource_type}
                    {event.resource_id ? `:${event.resource_id.slice(0, 8)}` : ''}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {event.decision || '-'}
                  </TableCell>
                </TableRow>
              ))}
              {(!data?.events || data.events.length === 0) && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                    No activity events found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
