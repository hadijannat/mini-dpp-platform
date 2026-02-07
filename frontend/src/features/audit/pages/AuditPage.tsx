import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import {
  Shield,
  CheckCircle,
  XCircle,
  RefreshCw,
  Hash,
} from 'lucide-react';
import { getApiErrorMessage, apiFetch } from '@/lib/api';
import { PageHeader } from '@/components/page-header';
import { LoadingSpinner } from '@/components/loading-spinner';
import { ErrorBanner } from '@/components/error-banner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface AuditEvent {
  id: string;
  tenant_id: string | null;
  subject: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  decision: string | null;
  ip_address: string | null;
  user_agent: string | null;
  metadata_: Record<string, unknown> | null;
  created_at: string;
  event_hash: string | null;
  prev_event_hash: string | null;
  chain_sequence: number | null;
}

interface AuditEventListResponse {
  items: AuditEvent[];
  total: number;
  page: number;
  page_size: number;
}

interface ChainVerificationResponse {
  is_valid: boolean;
  verified_count: number;
  first_break_at: number | null;
  errors: string[];
  tenant_id: string;
}

async function fetchAuditEvents(
  params: { page: number; action?: string; resource_type?: string; tenant_id?: string },
  token?: string,
) {
  const searchParams = new URLSearchParams();
  searchParams.set('page', String(params.page));
  searchParams.set('page_size', '25');
  if (params.action) searchParams.set('action', params.action);
  if (params.resource_type) searchParams.set('resource_type', params.resource_type);
  if (params.tenant_id) searchParams.set('tenant_id', params.tenant_id);

  const response = await apiFetch(
    `/api/v1/admin/audit/events?${searchParams.toString()}`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Failed to fetch audit events'));
  }
  return response.json() as Promise<AuditEventListResponse>;
}

async function verifyChain(tenantId: string, token?: string) {
  const response = await apiFetch(
    `/api/v1/admin/audit/verify/chain?tenant_id=${encodeURIComponent(tenantId)}`,
    {},
    token,
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, 'Chain verification failed'));
  }
  return response.json() as Promise<ChainVerificationResponse>;
}

export default function AuditPage() {
  const auth = useAuth();
  const token = auth.user?.access_token;
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('');
  const [verifyTenantId, setVerifyTenantId] = useState('');

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['audit-events', page, actionFilter, resourceFilter],
    queryFn: () =>
      fetchAuditEvents(
        {
          page,
          action: actionFilter || undefined,
          resource_type: resourceFilter || undefined,
        },
        token,
      ),
    enabled: Boolean(token),
  });

  const verifyMutation = useMutation({
    mutationFn: () => verifyChain(verifyTenantId.trim(), token),
  });

  const pageError =
    (verifyMutation.error as Error | undefined) ??
    (isError ? (error as Error) : undefined);
  const sessionExpired = Boolean(pageError?.message?.includes('Session expired'));

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault();
    if (verifyTenantId.trim()) {
      verifyMutation.mutate();
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Trail"
        description="Cryptographically verified event log"
      />

      {pageError && (
        <ErrorBanner
          message={pageError.message || 'Something went wrong.'}
          showSignIn={sessionExpired}
          onSignIn={() => { void auth.signinRedirect(); }}
        />
      )}

      {/* Chain verification */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Hash Chain Verification
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleVerify} className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="verify-tenant">Tenant ID</Label>
              <Input
                id="verify-tenant"
                type="text"
                value={verifyTenantId}
                onChange={(e) => setVerifyTenantId(e.target.value)}
                placeholder="Enter tenant UUID"
                required
              />
            </div>
            <Button type="submit" disabled={verifyMutation.isPending || !verifyTenantId.trim()}>
              {verifyMutation.isPending ? (
                <LoadingSpinner size="sm" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Verify Chain
            </Button>
          </form>

          {verifyMutation.data && (
            <div className="rounded-lg border p-4">
              <div className="flex items-center gap-3">
                {verifyMutation.data.is_valid ? (
                  <CheckCircle className="h-6 w-6 text-green-500" />
                ) : (
                  <XCircle className="h-6 w-6 text-red-500" />
                )}
                <div>
                  <p className="font-semibold">
                    {verifyMutation.data.is_valid ? 'Chain Valid' : 'Chain Broken'}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {verifyMutation.data.verified_count} events verified
                    {verifyMutation.data.first_break_at != null && (
                      <> &mdash; first break at sequence #{verifyMutation.data.first_break_at}</>
                    )}
                  </p>
                </div>
              </div>
              {verifyMutation.data.errors.length > 0 && (
                <ul className="mt-2 space-y-1 text-sm text-destructive">
                  {verifyMutation.data.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="w-48">
          <Select value={actionFilter || 'all'} onValueChange={(v) => { setActionFilter(v === 'all' ? '' : v); setPage(1); }}>
            <SelectTrigger>
              <SelectValue placeholder="Filter by action" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All actions</SelectItem>
              <SelectItem value="create_dpp">Create DPP</SelectItem>
              <SelectItem value="publish_dpp">Publish DPP</SelectItem>
              <SelectItem value="update_dpp">Update DPP</SelectItem>
              <SelectItem value="archive_dpp">Archive DPP</SelectItem>
              <SelectItem value="export_dpp">Export DPP</SelectItem>
              <SelectItem value="publish_to_dtr">Publish to DTR</SelectItem>
              <SelectItem value="publish_to_edc">Publish to EDC</SelectItem>
              <SelectItem value="compliance_check">Compliance Check</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-48">
          <Select value={resourceFilter || 'all'} onValueChange={(v) => { setResourceFilter(v === 'all' ? '' : v); setPage(1); }}>
            <SelectTrigger>
              <SelectValue placeholder="Filter by resource" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All resources</SelectItem>
              <SelectItem value="dpp">DPP</SelectItem>
              <SelectItem value="connector">Connector</SelectItem>
              <SelectItem value="template">Template</SelectItem>
              <SelectItem value="tenant">Tenant</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Events table */}
      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Decision</TableHead>
                <TableHead>Chain</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((event) => (
                <TableRow key={event.id}>
                  <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                    {new Date(event.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{event.action}</Badge>
                  </TableCell>
                  <TableCell className="text-sm">
                    {event.resource_type}
                    {event.resource_id && (
                      <span className="ml-1 font-mono text-xs text-muted-foreground">
                        {event.resource_id.slice(0, 8)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {event.subject ?? '-'}
                  </TableCell>
                  <TableCell>
                    {event.decision === 'allow' && (
                      <Badge variant="secondary" className="bg-green-100 text-green-800">allow</Badge>
                    )}
                    {event.decision === 'deny' && (
                      <Badge variant="destructive">deny</Badge>
                    )}
                    {!event.decision && <span className="text-muted-foreground">-</span>}
                  </TableCell>
                  <TableCell>
                    {event.event_hash ? (
                      <span className="flex items-center gap-1" title={event.event_hash}>
                        <Hash className="h-3 w-3 text-muted-foreground" />
                        <span className="font-mono text-xs">
                          {event.event_hash.slice(0, 12)}
                        </span>
                      </span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {data && data.total > 0 && (
            <div className="flex items-center justify-between border-t px-4 py-3">
              <p className="text-sm text-muted-foreground">
                {data.total} total events
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <span className="flex items-center text-sm text-muted-foreground px-2">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}

          {data && data.items.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No audit events found.
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
